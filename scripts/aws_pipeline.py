"""Usa OIDC de GitHub y SSM; no requiere claves AWS ni acceso publico a Kubernetes."""
import json
import os
import subprocess
import time
import urllib.request


def aws(*args):
    return json.loads(subprocess.check_output(['aws', *args, '--output', 'json', '--no-cli-pager']))


def main():
    request = urllib.request.Request(os.environ['ACTIONS_ID_TOKEN_REQUEST_URL'] + '&audience=sts.amazonaws.com',
        headers={'Authorization': 'bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    token = json.load(urllib.request.urlopen(request, timeout=30))['value']
    # Archivo temporal privado: el token no aparece en argumentos del proceso ni registros.
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as handle:
        handle.write(token)
        name = handle.name
    try:
        result = aws('sts', 'assume-role-with-web-identity', '--role-arn', os.environ['AWS_DEPLOY_ROLE'],
            '--role-session-name', 'github-' + os.environ['GITHUB_RUN_ID'], '--web-identity-token', 'file://' + name,
            '--duration-seconds', '3600')['Credentials']
    finally:
        os.unlink(name)
    for key, value in result.items():
        if key in ('AccessKeyId', 'SecretAccessKey', 'SessionToken'):
            print('::add-mask::' + value, flush=True)
    os.environ.update(AWS_ACCESS_KEY_ID=result['AccessKeyId'], AWS_SECRET_ACCESS_KEY=result['SecretAccessKey'],
                      AWS_SESSION_TOKEN=result['SessionToken'])
    parameters = {'Revision': [os.environ['DEPLOY_SHA']], 'Image': [os.environ['IMAGE']], 'Environment': [os.environ['DEPLOY_ENV']]}
    instance = os.environ['AWS_DEPLOY_INSTANCE']
    command = aws('ssm', 'send-command', '--instance-ids', instance, '--document-name', os.environ['AWS_DEPLOY_DOCUMENT'],
        '--parameters', json.dumps(parameters), '--timeout-seconds', '1200')['Command']['CommandId']
    print('Comando de despliegue AWS: ' + command, flush=True)
    for attempt in range(140):
        time.sleep(10)
        result = aws('ssm', 'get-command-invocation', '--command-id', command, '--instance-id', instance)
        status = result['Status']
        if status in ('Pending', 'InProgress', 'Delayed'):
            continue
        print(result.get('StandardOutputContent', ''))
        print(result.get('StandardErrorContent', ''))
        if status != 'Success':
            raise RuntimeError('SSM no completo el despliegue: ' + status)
        return
    raise TimeoutError('El despliegue AWS excedio el tiempo permitido')


if __name__ == '__main__':
    main()
