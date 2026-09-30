"""Verifica entornos activos y registra evidencia sin credenciales ni tokens."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from environment_config import credentials, ENVIRONMENTS, PORTS
from smoke import token

ROOT = Path(__file__).resolve().parents[1]


def main():
    urls = json.loads((ROOT / '.local/public_urls.json').read_text())
    configuration = {name: credentials(ROOT, name) for name in ENVIRONMENTS}
    for key in ('JWT_SECRET', 'REDIS_PASSWORD'):
        assert len({settings[key] for settings in configuration.values()}) == 3
    report = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'entornos': [],
              'secretos_independientes': True, 'rechazo_jwt_entre_entornos': []}
    for name in ENVIRONMENTS:
        subprocess.run([sys.executable, 'scripts/test_environment.py', name], cwd=ROOT, check=True)
        subprocess.run([sys.executable, 'scripts/test_environment.py', name, '--local'], cwd=ROOT, check=True)
        report['entornos'].append({'entorno': name, 'url': urls[name], 'pruebas_publicas': 'correctas',
                                  'pruebas_locales': 'correctas', 'namespace': 'devops-' + name})
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
                with urllib.request.urlopen(request, timeout=15) as response:
                    status = response.status
            except urllib.error.HTTPError as error:
                status = error.code
            assert status in (401, 403), (source, destination, status)
            report['rechazo_jwt_entre_entornos'].append({'origen': source, 'destino': destination, 'estado': status})
    report['metodos_especiales'] = []
    for channel, url in [('local', 'https://127.0.0.1:9443'), ('publico', urls['production'])]:
        for method in ('HEAD', 'TRACE'):
            request = urllib.request.Request(url + '/DevOps', method=method)
            context = ssl._create_unverified_context() if channel == 'local' else ssl.create_default_context()
            try:
                with urllib.request.urlopen(request, context=context, timeout=15) as response:
                    status, body = response.status, response.read().decode()
            except urllib.error.HTTPError as error:
                status, body = error.code, error.read().decode()
            assert status == 405
            assert body == ('' if method == 'HEAD' else 'ERROR'), (channel, method, body)
            report['metodos_especiales'].append({'canal': channel, 'metodo': method, 'estado': status,
                'tipo_cuerpo': 'vacio' if not body else 'ERROR' if body == 'ERROR' else 'HTML' if '<html>' in body else 'JSON'})
    (ROOT / 'evidence/cierre-entornos.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Tres entornos probados; seis cruces de JWT rechazados; TRACE devuelve ERROR y HEAD no contiene cuerpo.')


if __name__ == '__main__':
    main()
