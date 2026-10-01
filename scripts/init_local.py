"""Crea la configuración privada local. El inicio y el despliegue se ejecutan por separado."""
import json
import os
from pathlib import Path
import secrets
from kong_config import config
from environment_config import ensure_issuer_key

root = Path(__file__).resolve().parents[1]
env = root / '.env'
if not env.exists():
    env.write_text('API_KEY=2f5ae96c-b558-4c7b-a590-a501ae1c3f6c\n'
                   f'JWT_SECRET={secrets.token_hex(32)}\n'
                   f'REDIS_PASSWORD={secrets.token_hex(24)}\n', encoding='utf-8')
ensure_issuer_key(env)
for line in env.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        key, value = line.split('=', 1)
        os.environ[key] = value
(root / '.local').mkdir(exist_ok=True)
(root / '.local/kong.json').write_text(json.dumps(config(local=True), indent=2), encoding='utf-8')
print('Configuración privada preparada en .env y .local/kong.json. Estos archivos no se versionan.')
