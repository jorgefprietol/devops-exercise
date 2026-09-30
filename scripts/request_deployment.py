"""GitHub-hosted job requests a deployment and waits for the local agent."""
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
    'description': 'Deploy verified image to the local Kubernetes lab',
    'payload': {'image': os.environ['IMAGE'], 'run_id': os.environ['GITHUB_RUN_ID']},
    'production_environment': os.environ['DEPLOY_ENV'] == 'production'})
ident = deployment['id']
print(f'Deployment {ident}: waiting for the local Kubernetes agent.', flush=True)
for _ in range(120):
    statuses = api(f'/deployments/{ident}/statuses')
    if statuses:
        state = statuses[0]['state']
        if state == 'success':
            url = statuses[0].get('environment_url', '')
            print('Deployment and public HTTPS checks passed: ' + url, flush=True)
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
                summary.write(f'### Kubernetes deployment verified\n\n[Public API]({url}/DevOps) · deployment {ident}\n\nPOST with API Key and a fresh JWT is required.\n')
            break
        if state in ('failure', 'error', 'inactive'):
            raise RuntimeError('Local deployment reported ' + state)
    time.sleep(10)
else:
    api(f'/deployments/{ident}/statuses', {'state': 'error', 'description': 'Local agent did not finish within 20 minutes.'})
    raise TimeoutError('Start the local lab deployment agent and rerun the workflow.')
