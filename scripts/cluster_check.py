"""Comprueba nodos, réplicas, HPA y HTTPS por un canal local autenticado a Kubernetes."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from smoke import token


def kubectl(env):
    command = ['kubectl']
    if env.get('KUBECTL_CONTEXT'):
        command += ['--context', env['KUBECTL_CONTEXT']]
    return command


def wait_gateway(env, url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('La espera local solo admite HTTPS de loopback')
    body = json.dumps({'message': 'This is a test', 'to': 'Juan Perez',
                       'from': 'Rita Asturia', 'timeToLifeSec': 45}).encode()
    for attempt in range(6):
        # Es otra transacción de diagnóstico, con un jti nuevo en cada intento.
        request = urllib.request.Request(url + '/DevOps', data=body, headers={
            'Content-Type': 'application/json', 'X-Parse-REST-API-Key': env['API_KEY'],
            'X-JWT-KWY': token(env['JWT_SECRET'])})
        try:
            with urllib.request.urlopen(request, context=ssl._create_unverified_context(), timeout=12) as response:
                if response.status != 200 or json.loads(response.read()) != {'message': 'Hello Juan Perez your message will be sent'}:
                    raise RuntimeError('La respuesta de disponibilidad no cumple el contrato')
                return
        except urllib.error.HTTPError as error:
            if error.code not in (502, 503, 504) or attempt == 5:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 5:
                raise
        print('Esperando la disponibilidad del gateway después del rollout.', flush=True)
        time.sleep(2)


@contextmanager
def gateway_forward(env, namespace):
    if not re.fullmatch(r'devops-(production|staging|development)', namespace):
        raise ValueError('Namespace no permitido')
    with tempfile.TemporaryDirectory(prefix='devops-forward-') as folder:
        log_path = Path(folder) / 'kubectl.log'
        with log_path.open('wb') as log:
            process = subprocess.Popen(kubectl(env) + ['-n', namespace, 'port-forward',
                'service/kong', ':443', '--address=127.0.0.1'], env=env,
                stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    output = log_path.read_text(encoding='utf-8', errors='replace')
                    match = re.search(r'Forwarding from 127\.0\.0\.1:(\d+) ->', output)
                    if match:
                        yield 'https://127.0.0.1:' + match.group(1)
                        return
                    if process.poll() is not None:
                        raise RuntimeError('No se pudo abrir el acceso a Kong: ' + output[-1500:])
                    time.sleep(0.25)
                raise TimeoutError('Kubernetes no habilitó el acceso local a Kong en 45 segundos')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def verify_cluster(root, env, namespace):
    def get(*args):
        return json.loads(subprocess.check_output(kubectl(env) + ['-n', namespace, 'get',
            *args, '-o', 'json'], env=env, timeout=30))

    report = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'namespace': namespace,
              'canal': 'HTTPS local mediante kubectl port-forward; sin túnel público', 'replicas': {}}
    for app in ('devops-api', 'kong'):
        pods = get('pods', '-l', 'app=' + app)['items']
        ready = [pod for pod in pods if not pod['metadata'].get('deletionTimestamp')
                 and any(c['type'] == 'Ready' and c['status'] == 'True'
                         for c in pod.get('status', {}).get('conditions', []))]
        nodes = sorted({pod['spec']['nodeName'] for pod in ready})
        if len(ready) < 2 or len(nodes) < 2:
            raise RuntimeError(app + ': se requieren dos réplicas listas distribuidas en dos nodos')
        report['replicas'][app] = {'listas': len(ready), 'nodos': nodes}
    for attempt in range(30):
        hpa = get('hpa', 'devops-api')
        if any(c['type'] == 'ScalingActive' and c['status'] == 'True'
               for c in hpa.get('status', {}).get('conditions', [])):
            break
        if attempt == 29:
            raise RuntimeError('El HPA todavía no puede obtener métricas de CPU')
        time.sleep(3)
    report['hpa'] = {'minimo': hpa['spec']['minReplicas'], 'maximo': hpa['spec']['maxReplicas'],
                     'metricas_disponibles': True}
    with gateway_forward(env, namespace) as url:
        wait_gateway(env, url)
        subprocess.run([sys.executable, str(Path(root) / 'scripts/smoke.py'), url, '--local'],
                       cwd=root, env=env, check=True, timeout=120)
        if env.get('ISSUER_KEY'):
            subprocess.run([sys.executable, str(Path(root) / 'scripts/check_issuer.py'), url, '--local'],
                           cwd=root, env=env, check=True, timeout=120)
            report['emision_jwt'] = 'correcto'
    report['contrato_autenticacion_y_repeticiones'] = 'correcto'
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report
