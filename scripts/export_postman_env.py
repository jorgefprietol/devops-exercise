"""Exporta entornos privados para Postman sin imprimir sus credenciales."""
import json
import argparse
from pathlib import Path
import uuid

from environment_config import credentials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose-port', type=int, default=8443)
    args = parser.parse_args()
    if not 1024 <= args.compose_port <= 65535:
        parser.error('Puerto local no válido')
    root = Path(__file__).resolve().parents[1]
    output = root / '.local' / 'postman'
    output.mkdir(parents=True, exist_ok=True)
    urls_file = root / '.local' / 'public_urls.json'
    urls = json.loads(urls_file.read_text(encoding='utf-8-sig')) if urls_file.exists() else {}
    targets = [('Local_Compose', 'production', f'https://127.0.0.1:{args.compose_port}')]
    if (root / '.local/kubeconfig').exists():
        targets.append(('Local_Kubernetes', 'production', 'https://127.0.0.1:9443'))
    compose_url = root / '.local/compose_public_url.txt'
    if compose_url.exists():
        targets.append(('Publico_Compose', 'production', compose_url.read_text(encoding='utf-8').strip()))
    targets += [(f'Publico_{env}', env, url) for env, url in urls.items()]
    for name, env, url in targets:
        values = credentials(root, env)
        document = {
            'id': str(uuid.uuid4()), 'name': 'DevOps - ' + name,
            'values': [
                {'key': 'base_url', 'value': url.rstrip('/'), 'type': 'default', 'enabled': True},
                {'key': 'api_key', 'value': values['API_KEY'], 'type': 'secret', 'enabled': True},
                {'key': 'jwt_secret', 'value': values['JWT_SECRET'], 'type': 'secret', 'enabled': True},
            ],
            '_postman_variable_scope': 'environment',
        }
        path = output / (name + '.postman_environment.json')
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Entorno privado creado: ' + str(path))
        if values.get('ISSUER_KEY'):
            issuer_document = {**document, 'id': str(uuid.uuid4()), 'name': 'DevOps Emisor - ' + name,
                'values': [document['values'][0],
                    {'key': 'issuer_key', 'value': values['ISSUER_KEY'], 'type': 'secret', 'enabled': True}]}
            (output / ('Emisor_' + name + '.postman_environment.json')).write_text(
                json.dumps(issuer_document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Estos archivos contienen secretos. No los publiques ni los compartas.')


if __name__ == '__main__':
    main()
