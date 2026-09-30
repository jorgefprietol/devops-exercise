"""Publica la demostración HTTPS y verifica el contrato, incluido TRACE."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from environment_config import ENVIRONMENTS, credentials

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'pinggy/pinggy@sha256:15af4610028da251d36af2f6765693102a188e5628c033ac2ae42ab8ae7e25e7'
URL_PATTERN = r'https://[a-z0-9-]+\.(?:run\.pinggy-free\.link|free\.pinggy\.net)'


def checked_url(log):
    matches = re.findall(URL_PATTERN, log)
    return matches[0] if matches else None


def verify(url, environment):
    env = {**os.environ, **credentials(ROOT, environment), 'PYTHONUTF8': '1'}
    subprocess.run([sys.executable, str(ROOT / 'scripts/smoke.py'), url],
                   cwd=ROOT, env=env, check=True, timeout=90)


def wait_public(command, env, environment):
    for _ in range(45):
        result = subprocess.run(command, env=env, cwd=ROOT, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=20)
        url = checked_url(result.stdout)
        if url:
            for attempt in range(6):
                try:
                    verify(url, environment)
                    return url
                except subprocess.CalledProcessError:
                    if attempt == 5:
                        raise
                    time.sleep(3)
        time.sleep(2)
    raise RuntimeError('No se obtuvo una URL. Revisa los registros de public-tunnel y la conexión a Internet.')


def compose_url(project):
    url = wait_public(['docker', 'compose', '-p', project, '--profile', 'public',
                      'logs', '--no-color', '--tail', '100', 'public-tunnel'], os.environ, 'production')
    (ROOT / '.local/compose_public_url.txt').write_text(url + '\n', encoding='utf-8')
    return url


def kubernetes_url(environment, renew=False):
    env = {**os.environ, 'KUBECONFIG': str(ROOT / '.local/kubeconfig')}
    namespace = 'devops-' + environment
    command = ['kubectl', '-n', namespace]
    manifest = {
        'apiVersion': 'apps/v1', 'kind': 'Deployment',
        'metadata': {'name': 'public-tunnel', 'namespace': namespace},
        'spec': {'replicas': 1, 'selector': {'matchLabels': {'app': 'public-tunnel'}},
            'strategy': {'type': 'Recreate'},
            'template': {'metadata': {'labels': {'app': 'public-tunnel'}},
                'spec': {'automountServiceAccountToken': False,
                    'containers': [{'name': 'tunnel', 'image': IMAGE,
                        'command': ['pinggy'],
                        'args': ['-p', '443', '-R0:kong-tunnel:80', 'free.pinggy.io', 'x:httpsonly'],
                        'securityContext': {'allowPrivilegeEscalation': False,
                            'capabilities': {'drop': ['ALL']}, 'seccompProfile': {'type': 'RuntimeDefault'}},
                        'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'},
                                      'limits': {'cpu': '250m', 'memory': '128Mi'}}}]}}}}
    subprocess.run(command + ['apply', '-f', '-'], input=json.dumps(manifest),
                   text=True, env=env, check=True)
    if renew:
        subprocess.run(command + ['rollout', 'restart', 'deployment/public-tunnel'], env=env, check=True)
    subprocess.run(command + ['rollout', 'status', 'deployment/public-tunnel', '--timeout=180s'], env=env, check=True)
    url = wait_public(command + ['logs', 'deployment/public-tunnel', '--tail=100'], env, environment)
    path = ROOT / '.local/public_urls.json'
    urls = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    urls[environment] = url
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(urls, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=ENVIRONMENTS, nargs='?', default='production')
    parser.add_argument('--renew', action='store_true', help='Crear una nueva sesión y URL pública')
    args = parser.parse_args()
    url = kubernetes_url(args.environment, args.renew)
    subprocess.run([sys.executable, str(ROOT / 'scripts/export_postman_env.py')], check=True)
    print(f'API pública comprobada: {url}/DevOps')
    print('Sesión gratuita: hasta 60 minutos. --renew renueva la sesión y cambia la URL; requiere Internet.')


if __name__ == '__main__':
    main()
