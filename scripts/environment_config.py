"""Credenciales privadas e independientes por entorno; nunca se imprimen."""
from pathlib import Path
import secrets

ENVIRONMENTS = ('production', 'staging', 'development')
PORTS = {'production': 9443, 'staging': 9444, 'development': 9445}


def ensure_issuer_key(path):
    """Amplía una configuración existente sin rotar sus secretos."""
    if not any(line.startswith('ISSUER_KEY=') for line in path.read_text(encoding='utf-8-sig').splitlines()):
        with path.open('a', encoding='utf-8') as file:
            file.write('\nISSUER_KEY=' + secrets.token_hex(32) + '\n')


def credentials(root: Path, environment: str, create=False):
    if environment not in ENVIRONMENTS:
        raise ValueError('Entorno no permitido')
    path = root / '.env' if environment == 'production' else root / '.local' / 'environments' / (environment + '.env')
    if create and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        # El modo x impide sobrescribir credenciales de un entorno existente.
        with path.open('x', encoding='utf-8') as file:
            file.write('API_KEY=2f5ae96c-b558-4c7b-a590-a501ae1c3f6c\n'
                       f'JWT_SECRET={secrets.token_hex(32)}\n'
                       f'REDIS_PASSWORD={secrets.token_hex(24)}\n')
    if create:
        ensure_issuer_key(path)
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            if key in ('API_KEY', 'JWT_SECRET', 'REDIS_PASSWORD', 'ISSUER_KEY'):
                values[key] = value
    if not all(values.get(key) for key in ('API_KEY', 'JWT_SECRET', 'REDIS_PASSWORD')) or len(values['JWT_SECRET'].encode()) < 32:
        raise ValueError('Configuración privada incompleta')
    return values
