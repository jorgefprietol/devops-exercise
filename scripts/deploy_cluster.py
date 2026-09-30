"""Despliega la misma aplicación en un clúster existente y comprueba su funcionamiento."""
import argparse
import base64
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys

from cluster_check import kubectl, verify_cluster
from environment_config import ENVIRONMENTS

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True, help='Contexto explícito de kubectl; no cambia el contexto global')
    parser.add_argument('--environment', choices=ENVIRONMENTS, default='production')
    parser.add_argument('--image', default=(ROOT / 'infra/release-image.txt').read_text().strip())
    parser.add_argument('--profile', type=Path, help='Perfil JSON versionado del proveedor')
    parser.add_argument('--secrets-file', type=Path, help='Archivo privado con API_KEY, JWT_SECRET y REDIS_PASSWORD; también admite variables de entorno')
    parser.add_argument('--tls-cert', required=True, type=Path)
    parser.add_argument('--tls-key', required=True, type=Path)
    parser.add_argument('--lab', action='store_true', help='Solo laboratorio kind: usar NodePort en lugar de LoadBalancer')
    parser.add_argument('--public-url', help='Comprobación adicional del dominio HTTPS, con validación estricta del certificado')
    args = parser.parse_args()
    env = {**os.environ, 'KUBECTL_CONTEXT': args.context, 'DEPLOY_ENV': args.environment,
           'IMAGE': args.image, 'LAB_MODE': 'kind' if args.lab else 'cloud', 'PYTHONUTF8': '1'}
    if args.profile:
        profile = json.loads(args.profile.read_text(encoding='utf-8-sig'))
        allowed = {'STORAGE_CLASS', 'LOAD_BALANCER_CLASS', 'LOAD_BALANCER_ANNOTATIONS'}
        if not isinstance(profile, dict) or set(profile) - allowed or not all(isinstance(v, str) for v in profile.values()):
            raise ValueError('Perfil no válido: solo admite configuración de almacenamiento y balanceador')
        env.update(profile)
    if args.secrets_file:
        for line in args.secrets_file.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                if key in ('API_KEY', 'JWT_SECRET', 'REDIS_PASSWORD'):
                    env[key] = value
    for name in ('API_KEY', 'JWT_SECRET', 'REDIS_PASSWORD'):
        if not env.get(name):
            raise ValueError('Falta la variable privada ' + name)
    # Comprueba que certificado y clave correspondan antes de modificar Kubernetes.
    ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(args.tls_cert, args.tls_key)
    env['TLS_CRT_B64'] = base64.b64encode(args.tls_cert.read_bytes()).decode()
    env['TLS_KEY_B64'] = base64.b64encode(args.tls_key.read_bytes()).decode()
    command = kubectl(env)
    nodes = json.loads(subprocess.check_output(command + ['get', 'nodes', '-o', 'json'], env=env))['items']
    workers = [node for node in nodes if not node['spec'].get('unschedulable')
               and not any(t.get('effect') in ('NoSchedule', 'NoExecute') for t in node['spec'].get('taints', []))
               and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions'])]
    if len(workers) < 2:
        raise RuntimeError('Se requieren al menos dos nodos listos y disponibles para programar pods')
    storage = json.loads(subprocess.check_output(command + ['get', 'storageclass', '-o', 'json'], env=env))['items']
    selected = env.get('STORAGE_CLASS')
    if not any((s['metadata']['name'] == selected if selected else
                s['metadata'].get('annotations', {}).get('storageclass.kubernetes.io/is-default-class') == 'true') for s in storage):
        raise RuntimeError('Configura STORAGE_CLASS con una clase existente o prepara una clase predeterminada')
    subprocess.run(command + ['get', '--raw=/apis/metrics.k8s.io/v1beta1/nodes'],
                   env=env, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(ROOT / 'scripts/deploy.py')], env=env, cwd=ROOT, check=True)
    namespace = 'devops-' + args.environment
    for resource in ('statefulset/redis', 'deployment/devops-api', 'deployment/kong'):
        subprocess.run(command + ['-n', namespace, 'rollout', 'status', resource, '--timeout=300s'], env=env, check=True)
    report = verify_cluster(ROOT, env, namespace)
    if args.public_url:
        subprocess.run([sys.executable, str(ROOT / 'scripts/smoke.py'), args.public_url], env=env, check=True)
        report['https_publico'] = 'correcto'
    private = ROOT / '.local'
    private.mkdir(exist_ok=True)
    (private / ('verificacion-' + args.environment + '.json')).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    subprocess.run(command + ['-n', namespace, 'get', 'service/kong'], env=env, check=True)
    print('Aplicación y escalado verificados. La publicación externa solo está verificada si se indicó --public-url.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        sys.exit('No se completó el despliegue: ' + str(error))
