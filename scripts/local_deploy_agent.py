"""Procesa solicitudes verificadas del repositorio y conserva el acceso local al cluster.

Se inicia después de kind y del túnel HTTPS. Consulta GitHub mediante conexiones
salientes y excluye las ejecuciones originadas por solicitudes de cambios.
"""
from pathlib import Path
import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.local'
REPO = 'jorgefprietol/devops-exercise'
OWNER = 'jorgefprietol'

def gh(path, body=None):
    command = ['gh', 'api', f'repos/{REPO}/{path}']
    if body is not None: command += ['--method', 'POST', '--input', '-']
    result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
        capture_output=True, text=True, check=True, encoding='utf-8')
    return json.loads(result.stdout) if result.stdout.strip() else None

def status(ident, state, url, description):
    gh(f'deployments/{ident}/statuses', {'state': state, 'environment_url': url,
        'description': description[:140], 'auto_inactive': False})

def validate(deployment):
    if deployment['creator']['login'] != 'github-actions[bot]': return False
    target = deployment['environment']
    if target not in ('development', 'staging', 'production'): return False
    payload = deployment.get('payload', {})
    image = payload.get('image', '')
    if not re.fullmatch(re.escape('ghcr.io/' + REPO) + r'@sha256:[a-f0-9]{64}', image): return False
    run = gh('actions/runs/' + str(int(payload['run_id'])))
    if run['event'] not in ('push', 'workflow_dispatch'): return False
    if run['actor']['login'] != OWNER or run['path'] != '.github/workflows/ci-cd.yml': return False
    if run['head_repository']['full_name'] != REPO: return False
    jobs = gh('actions/runs/' + str(run['id']) + '/jobs?per_page=100')['jobs']
    expected = ({'build', 'Compilación'}, {'test', 'Pruebas'}, {'package', 'Imagen Docker'})
    if not all(any(j['name'] in names and j['conclusion'] == 'success' for j in jobs) for names in expected): return False
    sha = deployment['sha']
    if not re.fullmatch('[a-f0-9]{40}', sha): return False
    subprocess.run(['git', 'fetch', 'origin', 'master', '--tags'], cwd=ROOT, check=True, capture_output=True)
    subprocess.run(['git', 'fetch', 'origin', sha], cwd=ROOT, check=True, capture_output=True)
    if target == 'production':
        if subprocess.run(['git', 'merge-base', '--is-ancestor', sha, 'origin/master'], cwd=ROOT).returncode: return False
    else:
        if subprocess.run(['git', 'cat-file', '-e', sha + '^{commit}'], cwd=ROOT).returncode: return False
    return True

def deploy(deployment, public_url):
    sha = deployment['sha']
    output = PRIVATE / 'releases' / sha
    output.mkdir(parents=True, exist_ok=True)
    archive = subprocess.check_output(['git', 'archive', '--format=zip', sha], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        for name in package.namelist():
            resolved = (output / name).resolve()
            if not resolved.is_relative_to(output.resolve()): raise ValueError('Ruta no permitida dentro del archivo')
        package.extractall(output)
    env = os.environ.copy()
    for line in (ROOT / '.env').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            env[key] = value
    env.update(KUBECONFIG=str(PRIVATE / 'kubeconfig'), LAB_MODE='kind',
               DEPLOY_ENV=deployment['environment'], IMAGE=deployment['payload']['image'])
    for key, file in [('TLS_CRT_B64', 'tls.crt'), ('TLS_KEY_B64', 'tls.key')]:
        env[key] = base64.b64encode((PRIVATE / file).read_bytes()).decode()
    subprocess.run([sys.executable, 'scripts/deploy.py'], cwd=output, env=env, check=True)
    for resource in ['statefulset/redis', 'deployment/devops-api', 'deployment/kong']:
        subprocess.run(['kubectl', '-n', 'devops-' + env['DEPLOY_ENV'], 'rollout', 'status', resource, '--timeout=300s'], env=env, check=True)
    subprocess.run([sys.executable, 'scripts/smoke.py', public_url], cwd=output, env=env, check=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=float, default=8)
    args = parser.parse_args()
    state_file = PRIVATE / 'agent-processed.json'
    processed = set(json.loads(state_file.read_text())) if state_file.exists() else set()
    end = time.monotonic() + args.hours * 3600
    print(f'Esperando despliegues verificados de {REPO}; sesión de {args.hours} horas.', flush=True)
    while time.monotonic() < end:
        try:
            for item in reversed(gh('deployments?per_page=10')):
                ident = item['id']
                if ident in processed: continue
                previous = gh(f'deployments/{ident}/statuses')
                if previous and previous[0]['state'] in ('success', 'failure', 'error', 'inactive'):
                    processed.add(ident)
                    continue
                if not validate(item): continue
                urls = json.loads((PRIVATE / 'public_urls.json').read_text())
                url = urls.get(item['environment'])
                if not url:
                    status(ident, 'failure', '', 'Inicia primero el túnel HTTPS del entorno seleccionado.')
                    processed.add(ident)
                    continue
                status(ident, 'in_progress', url, 'Aplicando la imagen verificada en Kubernetes local.')
                try:
                    deploy(item, url)
                    status(ident, 'success', url, 'Despliegue y pruebas HTTPS públicas completados correctamente.')
                    print(f'Despliegue {ident}: CORRECTO {url}', flush=True)
                except Exception as error:
                    status(ident, 'failure', url, 'Falló el despliegue local; revisa el registro del agente.')
                    print(f'Despliegue {ident}: ERROR {type(error).__name__}', flush=True)
                processed.add(ident)
                state_file.write_text(json.dumps(sorted(processed)))
        except Exception as error:
            print(f'Consulta del agente: {type(error).__name__}; se reintentará.', flush=True)
        time.sleep(15)

if __name__ == '__main__': main()
