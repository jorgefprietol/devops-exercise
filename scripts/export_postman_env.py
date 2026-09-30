"""Exporta entornos privados para Postman sin imprimir sus credenciales."""
import json
from pathlib import Path
import uuid

from environment_config import credentials


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / '.local' / 'postman'
    output.mkdir(parents=True, exist_ok=True)
    urls_file = root / '.local' / 'public_urls.json'
    urls = json.loads(urls_file.read_text(encoding='utf-8-sig')) if urls_file.exists() else {}
    targets = [('Local_Compose', 'production', 'https://127.0.0.1:8443')]
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
    print('Estos archivos contienen secretos. No los publiques ni los compartas.')


if __name__ == '__main__':
    main()
