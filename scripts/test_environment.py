"""Prueba pública con credenciales del entorno seleccionado, sin SDK adicional."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from environment_config import credentials, ENVIRONMENTS, PORTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('environment', nargs='?', default='production', choices=ENVIRONMENTS)
    parser.add_argument('--url')
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    url = args.url or (f'https://127.0.0.1:{PORTS[args.environment]}' if args.local else
                      json.loads((root / '.local/public_urls.json').read_text())[args.environment])
    env = {**os.environ, **credentials(root, args.environment)}
    command = [sys.executable, 'scripts/smoke.py', url]
    if args.local:
        command.append('--local')
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in ('127.0.0.1', 'localhost'):
            parser.error('--local solo admite HTTPS en loopback')
        # Tras un rollout, el primer acceso puede hacer que kubectl detecte
        # el pod anterior y el supervisor reconecte. No reintentamos un POST.
        for attempt in range(10):
            try:
                request = urllib.request.Request(url.rstrip('/') + '/DevOps', method='HEAD')
                urllib.request.urlopen(request, context=ssl._create_unverified_context(), timeout=3).close()
                break
            except urllib.error.HTTPError as error:
                if error.code == 405:
                    break
                raise
            except (urllib.error.URLError, TimeoutError):
                if attempt == 9:
                    raise
                time.sleep(2)
    subprocess.run(command, cwd=root, env=env, check=True)
    print('Entorno verificado: ' + args.environment)


if __name__ == '__main__':
    main()
