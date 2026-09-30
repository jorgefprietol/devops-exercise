"""Prepara un namespace conservando secretos y datos de instalaciones anteriores."""
from pathlib import Path
import argparse
import base64
import os
import subprocess
import sys
from environment_config import credentials, ENVIRONMENTS

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('environment', choices=ENVIRONMENTS)
    parser.add_argument('--image', required=True, help='Imagen verificada identificada por digest')
    args = parser.parse_args()
    env = os.environ.copy()
    env.update(credentials(ROOT, args.environment, create=True))
    env.update(KUBECONFIG=str(ROOT / '.local/kubeconfig'), KUBECTL_CONTEXT='kind-devops-lab', LAB_MODE='kind',
               DEPLOY_ENV=args.environment, IMAGE=args.image)
    for key, name in [('TLS_CRT_B64', 'tls.crt'), ('TLS_KEY_B64', 'tls.key')]:
        env[key] = base64.b64encode((ROOT / '.local' / name).read_bytes()).decode()
    subprocess.run([sys.executable, 'scripts/deploy.py'], cwd=ROOT, env=env, check=True)
    for resource in ('statefulset/redis', 'deployment/devops-api', 'deployment/kong'):
        subprocess.run(['kubectl', '-n', 'devops-' + args.environment, 'rollout', 'status',
                        resource, '--timeout=300s'], env=env, check=True)
    print('Entorno preparado: ' + args.environment)


if __name__ == '__main__':
    main()
