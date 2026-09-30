"""Verifica tres entornos y aislamiento de JWT; la entrada pública es opcional."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

from cluster_check import gateway_forward, verify_cluster
from environment_config import credentials, ENVIRONMENTS
from smoke import token

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', action='store_true', help='Comprobar además las URLs públicas configuradas')
    args = parser.parse_args()
    configuration = {name: credentials(ROOT, name) for name in ENVIRONMENTS}
    for key in ('JWT_SECRET', 'REDIS_PASSWORD'):
        assert len({settings[key] for settings in configuration.values()}) == 3
    env = {**os.environ, 'KUBECONFIG': str(ROOT / '.local/kubeconfig'), 'KUBECTL_CONTEXT': 'kind-devops-lab', 'PYTHONUTF8': '1'}
    report = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'entornos': [],
              'secretos_independientes': True, 'rechazo_jwt_entre_entornos': [], 'requiere_tunel_publico': False}
    with ExitStack() as stack:
        urls = {}
        for name in ENVIRONMENTS:
            target_env = {**env, **configuration[name]}
            result = verify_cluster(ROOT, target_env, 'devops-' + name)
            urls[name] = stack.enter_context(gateway_forward(target_env, 'devops-' + name))
            report['entornos'].append({'entorno': name, 'pruebas_locales': 'correctas', 'cluster': result})
            if args.public:
                subprocess.run([sys.executable, 'scripts/test_environment.py', name], cwd=ROOT, check=True)
                report['entornos'][-1]['pruebas_publicas'] = 'correctas'
        data = json.dumps({'message': 'This is a test', 'to': 'Juan Perez', 'from': 'Rita Asturia', 'timeToLifeSec': 45}).encode()
        for source in ENVIRONMENTS:
            os.environ.update(configuration[source])
            for destination in ENVIRONMENTS:
                if source == destination:
                    continue
                request = urllib.request.Request(urls[destination] + '/DevOps', data=data, headers={
                    'Content-Type': 'application/json', 'X-Parse-REST-API-Key': configuration[source]['API_KEY'],
                    'X-JWT-KWY': token()})
                try:
                    with urllib.request.urlopen(request, context=ssl._create_unverified_context(), timeout=15) as response:
                        status = response.status
                except urllib.error.HTTPError as error:
                    status = error.code
                assert status in (401, 403), (source, destination, status)
                report['rechazo_jwt_entre_entornos'].append({'origen': source, 'destino': destination, 'estado': status})
    (ROOT / 'evidence/cierre-entornos.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Tres entornos verificados sin túnel; seis cruces de JWT rechazados; TRACE ERROR y HEAD vacío.')


if __name__ == '__main__':
    main()
