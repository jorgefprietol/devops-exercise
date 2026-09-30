"""Solicita el despliegue desde GitHub y espera el resultado del agente local."""
import json
import os
import time
import urllib.request

repo = os.environ['GITHUB_REPOSITORY']

def api(path, body=None):
    request = urllib.request.Request('https://api.github.com/repos/' + repo + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

deployment = api('/deployments', {
    'ref': os.environ['DEPLOY_SHA'], 'environment': os.environ['DEPLOY_ENV'],
    'auto_merge': False, 'required_contexts': [],
    'description': 'Desplegar la imagen verificada en Kubernetes local',
    'payload': {'image': os.environ['IMAGE'], 'run_id': os.environ['GITHUB_RUN_ID']},
    'production_environment': os.environ['DEPLOY_ENV'] == 'production'})
ident = deployment['id']
print(f'Despliegue {ident}: esperando al agente local de Kubernetes.', flush=True)
for _ in range(120):
    statuses = api(f'/deployments/{ident}/statuses')
    if statuses:
        state = statuses[0]['state']
        if state == 'success':
            url = statuses[0].get('environment_url', '')
            print('Despliegue y pruebas HTTPS públicas correctos: ' + url, flush=True)
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
                summary.write(f'### Despliegue Kubernetes verificado\n\n[API pública]({url}/DevOps) · despliegue {ident}\n\nSe requiere POST, API Key y un JWT nuevo.\n')
            break
        if state in ('failure', 'error', 'inactive'):
            raise RuntimeError('El despliegue local comunicó el estado ' + state)
    time.sleep(10)
else:
    api(f'/deployments/{ident}/statuses', {'state': 'error', 'description': 'El agente local no terminó en 20 minutos.'})
    raise TimeoutError('Inicia el agente local y vuelve a ejecutar el flujo.')
