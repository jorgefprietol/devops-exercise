"""Emite un JWT de un solo uso para entregarlo al evaluador, sin exponer la firma."""
import argparse
from pathlib import Path
import sys

from environment_config import credentials, ENVIRONMENTS
from smoke import token


def issue(root, environment, secrets_file=None):
    if secrets_file is None:
        secret = credentials(root, environment)['JWT_SECRET']
    else:
        values = dict(line.split('=', 1) for line in Path(secrets_file).read_text(encoding='utf-8-sig').splitlines()
                      if '=' in line and not line.startswith('#'))
        secret = values.get('JWT_SECRET', '')
        if len(secret.encode()) < 32:
            raise ValueError('Configuración privada incompleta')
    return token(secret)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=ENVIRONMENTS, default='production')
    parser.add_argument('--secrets-file', type=Path, help='Archivo privado explícito para un despliegue cloud')
    args = parser.parse_args()
    try:
        result = issue(Path(__file__).resolve().parents[1], args.environment, args.secrets_file)
    except (OSError, ValueError):
        sys.exit('No se pudo leer la configuración privada del entorno. Inícialo primero; consulta HOST_JWT.md.')
    # Solo el token en stdout permite guardarlo en una variable sin otros mensajes.
    print(result)


if __name__ == '__main__':
    main()
