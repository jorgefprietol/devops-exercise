"""Administracion de esta pila desde AWS CloudShell, sin claves permanentes."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import time

STACK = 'devops-evaluacion'
REGION = 'us-east-2'


def aws(*args):
    result = subprocess.check_output(['aws', *args, '--region', REGION, '--output', 'json', '--no-cli-pager'], text=True)
    return json.loads(result) if result.strip() else {}


def outputs():
    stack = aws('cloudformation', 'describe-stacks', '--stack-name', STACK)['Stacks'][0]
    if stack['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE'):
        raise RuntimeError('La pila no esta preparada: ' + stack['StackStatus'])
    return {item['OutputKey']: item['OutputValue'] for item in stack['Outputs']}


def wait(command, instance):
    print('Comando SSM: ' + command, flush=True)
    for attempt in range(150):
        time.sleep(10)
        result = aws('ssm', 'get-command-invocation', '--command-id', command, '--instance-id', instance)
        if result['Status'] in ('Pending', 'InProgress', 'Delayed'):
            if attempt % 6 == 0:
                print('En ejecucion...', flush=True)
            continue
        print(result.get('StandardOutputContent', ''))
        print(result.get('StandardErrorContent', ''))
        if result['Status'] != 'Success':
            raise RuntimeError('Resultado SSM: ' + result['Status'])
        return
    raise TimeoutError('El comando no termino; consulta SSM antes de repetirlo')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status', 'initialize', 'deploy', 'token', 'destroy'))
    parser.add_argument('--accept-certificate-terms', action='store_true')
    parser.add_argument('--environment', choices=('production', 'staging', 'development'), default='production')
    parser.add_argument('--revision')
    parser.add_argument('--image')
    args = parser.parse_args()
    if args.action == 'status':
        print(json.dumps(aws('cloudformation', 'describe-stacks', '--stack-name', STACK), indent=2))
        print(json.dumps(aws('ssm', 'describe-instance-information'), indent=2))
        return
    if args.action == 'destroy':
        # Solo esta pila; nunca busca ni borra recursos de otros proyectos.
        aws('cloudformation', 'delete-stack', '--stack-name', STACK)
        print('Eliminacion solicitada; espera DELETE_COMPLETE antes de darla por terminada.')
        return
    values = outputs()
    instance = values['ServerId']
    if args.action == 'deploy':
        if not re.fullmatch(r'[a-f0-9]{40}', args.revision or ''):
            parser.error('--revision requiere el SHA completo')
        if not re.fullmatch(r'ghcr.io/jorgefprietol/devops-exercise@sha256:[a-f0-9]{64}', args.image or ''):
            parser.error('--image requiere la imagen publica con digest SHA256')
        name = values['DeployDocument']
        parameters = {'Revision': [args.revision], 'Image': [args.image], 'Environment': [args.environment]}
    else:
        name = 'AWS-RunShellScript'
        if args.action == 'initialize':
            if not args.accept_certificate_terms:
                parser.error('Confirma los terminos de Let\'s Encrypt antes de usar --accept-certificate-terms')
            ip = values['PublicIp']
            import ipaddress
            ipaddress.ip_address(ip)
            commands = ['set -eu', 'test -f /opt/devops/bootstrap-completo', 'kubectl get nodes -o wide',
                '/opt/devops/certbot/bin/certbot certonly --standalone --non-interactive --agree-tos '
                '--register-unsafely-without-email --preferred-profile shortlived --ip-address ' + ip]
        else:
            if not re.fullmatch(r'[a-f0-9]{40}', args.revision or ''):
                parser.error('--revision requiere el SHA desplegado')
            commands = ['python3 /opt/devops/releases/' + args.revision + '/scripts/issue_jwt.py --secrets-file /opt/devops/private/' + args.environment + '.env']
        parameters = {'commands': commands, 'executionTimeout': ['1200']}
    command = aws('ssm', 'send-command', '--instance-ids', instance, '--document-name', name,
        '--parameters', json.dumps(parameters), '--timeout-seconds', '1200')['Command']['CommandId']
    wait(command, instance)


if __name__ == '__main__':
    main()
