"""Prueba pública con credenciales del entorno seleccionado, sin SDK adicional."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
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
    subprocess.run(command, cwd=root, env=env, check=True)
    print('Entorno verificado: ' + args.environment)


if __name__ == '__main__':
    main()
