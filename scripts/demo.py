"""Inicia y comprueba el ejercicio con Docker y Python, sin SDK .NET local."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import ssl

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8443, help='Puerto HTTPS local; predeterminado 8443')
    parser.add_argument('--project', default='jorge-devops-exercise', help='Nombre del proyecto Docker Compose')
    parser.add_argument('--subnet', default=None, help='Subred libre de Docker si existe un conflicto')
    parser.add_argument('--stop', action='store_true', help='Detener los contenedores conservando los datos')
    parser.add_argument('--test-only', action='store_true', help='Comprobar el entorno que ya está iniciado')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,50}', args.project):
        parser.error('Puerto o nombre de proyecto no válido')
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['LAB_PORT'] = str(args.port)
    if args.subnet:
        import ipaddress
        network = ipaddress.ip_network(args.subnet)
        if network.version != 4 or not network.is_private:
            parser.error('Utiliza una subred IPv4 privada libre')
        env['LAB_SUBNET'] = str(network)
    compose = ['docker', 'compose', '-p', args.project]

    def run(command):
        subprocess.run(command, cwd=ROOT, env=env, check=True)

    run([sys.executable, 'scripts/init_local.py'])
    for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            env[key] = value
    if args.stop:
        run(compose + ['down'])
        print('Contenedores detenidos; datos de Redis conservados.')
        return
    if not args.test_only:
        run(['docker', 'info', '--format', '{{.OSType}}'])
        run(compose + ['build', 'api1'])
        run(compose + ['up', '-d', '--no-build', '--force-recreate', '--wait', '--wait-timeout', '180'])
    url = f'https://127.0.0.1:{args.port}'
    run([sys.executable, 'scripts/smoke.py', url, '--local'])
    # El certificado autofirmado solo se acepta en esta dirección de loopback.
    os.environ.update({key: env[key] for key in ('API_KEY', 'JWT_SECRET')})
    from smoke import token
    body = {'message': 'This is a test', 'to': 'Juan Perez', 'from': 'Rita Asturia', 'timeToLifeSec': 45}
    request = urllib.request.Request(url + '/DevOps', data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'X-Parse-REST-API-Key': env['API_KEY'], 'X-JWT-KWY': token()})
    with urllib.request.urlopen(request, context=ssl._create_unverified_context(), timeout=15) as response:
        print(response.read().decode())
    run(compose + ['ps'])
    print(f'API local comprobada: {url}/DevOps. El navegador utiliza GET; para probar POST ejecuta este script.')


if __name__ == '__main__':
    try:
        main()
    except (subprocess.CalledProcessError, OSError, ValueError) as error:
        sys.exit(f'No se completó la demostración: {error}. Revisa Docker y los puertos; consulta README.txt.')
