"""Creates private local configuration once. Does not start Docker or deploy."""
import json
import os
from pathlib import Path
import secrets
from kong_config import config

root = Path(__file__).resolve().parents[1]
env = root / '.env'
if not env.exists():
    env.write_text('API_KEY=2f5ae96c-b558-4c7b-a590-a501ae1c3f6c\n'
                   f'JWT_SECRET={secrets.token_hex(32)}\n'
                   f'REDIS_PASSWORD={secrets.token_hex(24)}\n', encoding='utf-8')
for line in env.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        key, value = line.split('=', 1)
        os.environ[key] = value
(root / '.local').mkdir(exist_ok=True)
(root / '.local/kong.json').write_text(json.dumps(config(local=True), indent=2), encoding='utf-8')
print('Private .env and .local/kong.json ready. Do not commit them.')
