"""Aplica la imagen en K3s de AWS conservando credenciales privadas por entorno."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request
from environment_config import ensure_issuer_key

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path('/opt/devops/private')


def public_ip():
    request = urllib.request.Request('http://169.254.169.254/latest/api/token', method='PUT',
        headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'})
    token = urllib.request.urlopen(request, timeout=5).read().decode()
    request = urllib.request.Request('http://169.254.169.254/latest/meta-data/public-ipv4',
        headers={'X-aws-ec2-metadata-token': token})
    return urllib.request.urlopen(request, timeout=5).read().decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=('production', 'staging', 'development'), required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    credentials = PRIVATE / (args.environment + '.env')
    if not credentials.exists():
        credentials.write_text('API_KEY=2f5ae96c-b558-4c7b-a590-a501ae1c3f6c\nJWT_SECRET=' +
            secrets.token_hex(32) + '\nREDIS_PASSWORD=' + secrets.token_hex(32) + '\n')
    ensure_issuer_key(credentials)
    ip = public_ip()
    cert = Path('/etc/letsencrypt/live') / ip
    if not (cert / 'fullchain.pem').exists():
        raise RuntimeError('Primero emite el certificado HTTPS con Certbot segun AWS.md')
    env = {**os.environ, 'KUBECONFIG': '/etc/rancher/k3s/k3s.yaml',
        'STORAGE_CLASS': 'local-path', 'GATEWAY_SERVICE_TYPE': 'LoadBalancer' if args.environment == 'production' else 'ClusterIP'}
    for attempt in range(60):
        nodes = json.loads(subprocess.check_output(['kubectl', 'get', 'nodes', '-o', 'json'], env=env))['items']
        if sum(any(c['type'] == 'Ready' and c['status'] == 'True' for c in n['status']['conditions']) for n in nodes) >= 2:
            break
        time.sleep(5)
    command = [sys.executable, str(ROOT / 'scripts/deploy_cluster.py'), '--context', 'default',
        '--environment', args.environment, '--image', args.image, '--secrets-file', str(credentials),
        '--tls-cert', str(cert / 'fullchain.pem'), '--tls-key', str(cert / 'privkey.pem')]
    if args.environment == 'production':
        command += ['--public-url', 'https://' + ip]
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    print('AWS: entorno ' + args.environment + ' verificado')


if __name__ == '__main__':
    main()
