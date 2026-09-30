"""Emite un JWT de un solo uso para entregarlo al evaluador, sin exponer la firma."""
import argparse
from pathlib import Path
import sys

from environment_config import credentials, ENVIRONMENTS
from smoke import token


def issue(root, environment):
    return token(credentials(root, environment)['JWT_SECRET'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=ENVIRONMENTS, default='production')
    args = parser.parse_args()
    try:
        result = issue(Path(__file__).resolve().parents[1], args.environment)
    except (OSError, ValueError):
        sys.exit('No se pudo leer la configuración privada del entorno. Inícialo primero; consulta HOST_JWT.md.')
    # Solo el token en stdout permite guardarlo en una variable sin otros mensajes.
    print(result)


if __name__ == '__main__':
    main()
