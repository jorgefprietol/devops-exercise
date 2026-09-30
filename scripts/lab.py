"""Prepara Kubernetes con dos trabajadores, red, métricas y la aplicación."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from cluster_check import verify_cluster
from environment_config import credentials

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.local'
NODE = 'kindest/node:v1.34.11@sha256:44e222ee2132dab25ff87301682f89eb82c7880ea3a1bf543bfe9708fd08d67d'


def install_tool(name):
    extension = '.exe' if os.name == 'nt' else ''
    target = PRIVATE / 'bin' / (name + extension)
    if target.exists() or shutil.which(name):
        return
    system = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'darwin'}[platform.system()]
    arch = {'AMD64': 'amd64', 'x86_64': 'amd64', 'arm64': 'arm64', 'aarch64': 'arm64'}[platform.machine()]
    if name == 'kind':
        url = f'https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-{system}-{arch}'
    else:
        url = f'https://dl.k8s.io/release/v1.34.11/bin/{system}/{arch}/kubectl{extension}'
    print('Descargando herramienta privada: ' + name, flush=True)
    content = urllib.request.urlopen(url, timeout=120).read()
    expected = urllib.request.urlopen(url + '.sha256sum' if name == 'kind' else url + '.sha256', timeout=30).read().decode().split()[0]
    if hashlib.sha256(content).hexdigest() != expected:
        raise RuntimeError('La suma SHA-256 no coincide: ' + name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    target.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', action='store_true', help='Publicar HTTPS temporal y probar el contrato')
    parser.add_argument('--all-environments', action='store_true', help='Preparar también staging y development')
    parser.add_argument('--image', default=(ROOT / 'infra/release-image.txt').read_text().strip(), help='Imagen por digest; predeterminada: versión verificada publicada')
    args = parser.parse_args()
    if not shutil.which('docker'):
        raise RuntimeError('Instala e inicia Docker Desktop con contenedores Linux antes de continuar.')
    PRIVATE.mkdir(exist_ok=True)
    env = {**os.environ, 'PYTHONUTF8': '1', 'KUBECONFIG': str(PRIVATE / 'kubeconfig'), 'KUBECTL_CONTEXT': 'kind-devops-lab'}
    env['PATH'] = str(PRIVATE / 'bin') + os.pathsep + env['PATH']

    def run(command, **kwargs):
        # En Windows, CreateProcess no busca ejecutables en el PATH de env.
        executable = shutil.which(command[0], path=env['PATH']) or command[0]
        command = [executable, *command[1:]]
        return subprocess.run(command, cwd=ROOT, env=env, check=True, **kwargs)

    run(['docker', 'info', '--format', '{{.OSType}}'])
    for name in ('kind', 'kubectl'):
        install_tool(name)
    clusters = run(['kind', 'get', 'clusters'], capture_output=True, text=True).stdout.splitlines()
    if 'devops-lab' not in clusters:
        run(['kind', 'create', 'cluster', '--config', 'infra/kind.yaml', '--kubeconfig', env['KUBECONFIG'], '--image', NODE])
    else:
        run(['docker', 'start', 'devops-lab-control-plane', 'devops-lab-worker', 'devops-lab-worker2'])
        run(['kind', 'export', 'kubeconfig', '--name', 'devops-lab', '--kubeconfig', env['KUBECONFIG']])
    for attempt in range(45):
        try:
            run(['kubectl', 'get', '--raw=/readyz', '--request-timeout=5s'], capture_output=True)
            break
        except subprocess.CalledProcessError:
            if attempt == 44:
                raise
            time.sleep(2)
    run([sys.executable, 'scripts/init_local.py'])
    # Entorno virtual privado: no modifica el Python global del evaluador.
    venv = PRIVATE / 'lab-venv'
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        run([sys.executable, '-m', 'venv', str(venv)])
    run([str(python), '-m', 'pip', 'install', '-r', 'infra/requirements-lab.txt', '--disable-pip-version-check'])
    run([str(python), 'scripts/bootstrap_addons.py'])
    run(['kubectl', 'wait', '--for=condition=Ready', 'nodes', '--all', '--timeout=300s'])
    run(['kubectl', '-n', 'kube-system', 'rollout', 'status', 'deployment/metrics-server', '--timeout=300s'])
    targets = ['production', 'staging', 'development'] if args.all_environments else ['production']
    for target in targets:
        run([sys.executable, 'scripts/prepare_environment.py', target, '--image', args.image])
        verify_cluster(ROOT, {**env, **credentials(ROOT, target)}, 'devops-' + target)
        if target == 'production':
            run([sys.executable, 'scripts/test_environment.py', target, '--local'])
        if args.public:
            run([sys.executable, 'scripts/public_tunnel.py', target])
    run([sys.executable, 'scripts/export_postman_env.py'])
    run(['kubectl', 'get', 'nodes', '-o', 'wide'])
    run(['kubectl', '-n', 'devops-production', 'get', 'pods,hpa'])
    print('Laboratorio preparado: dos trabajadores, Kong, dos réplicas de API, Redis, HPA y métricas.')
    print('API HTTPS local: https://127.0.0.1:9443/DevOps. Credenciales y Postman en .local.')
    print('GitHub Actions requiere configurar el repositorio del propietario; el script no solicita acceso a GitHub.')


if __name__ == '__main__':
    try:
        main()
    except (subprocess.CalledProcessError, OSError, ValueError, RuntimeError) as error:
        sys.exit('No se completó el laboratorio: ' + str(error))
