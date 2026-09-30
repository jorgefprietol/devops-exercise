"""Mantiene el acceso TLS de un entorno kind durante cambios de pods de Kong."""
from pathlib import Path
import argparse
import os
import subprocess
import time
from environment_config import PORTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('environment', choices=('staging', 'development'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, 'KUBECONFIG': str(root / '.local/kubeconfig')}
    command = ['kubectl', '-n', 'devops-' + args.environment, 'port-forward',
               'service/kong', str(PORTS[args.environment]) + ':443', '--address=127.0.0.1']
    while True:
        # kubectl termina al sustituirse el pod; el supervisor restablece la conexión.
        subprocess.run(command, env=env, check=False)
        time.sleep(2)


if __name__ == '__main__':
    main()
