"""Comprueba emisión autenticada, contrato y rechazo de reutilización sin imprimir secretos."""
import argparse
import json
import os
import ssl
import urllib.error
import urllib.request


def check(base, local=False):
    if local and not base.startswith('https://127.0.0.1:'):
        raise ValueError('La excepción TLS solo admite loopback')
    context = ssl._create_unverified_context() if local else ssl.create_default_context()

    def request(path, headers, body=b''):
        req = urllib.request.Request(base.rstrip('/') + path, data=body, headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=20, context=context)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    status, _, _ = request('/auth/token', {})
    assert status == 401, f'Emisión sin credencial: {status}'
    tokens = []
    for _ in range(2):
        status, body, headers = request('/auth/token', {'X-Evaluation-Key': os.environ['ISSUER_KEY']})
        assert status == 200, f'Emisión autenticada: {status}'
        result = json.loads(body)
        assert result['expires_in'] == 300 and result['header'] == 'X-JWT-KWY'
        assert headers['Cache-Control'] == 'no-store'
        tokens.append(result['token'])
    assert tokens[0] != tokens[1], 'Las emisiones deben generar tokens distintos'
    payload = json.dumps({'message': 'This is a test', 'to': 'Juan Perez', 'from': 'Rita Asturia', 'timeToLifeSec': 45}).encode()
    headers = {'X-Parse-REST-API-Key': os.environ['API_KEY'], 'X-JWT-KWY': tokens[0], 'Content-Type': 'application/json'}
    status, body, _ = request('/DevOps', headers, payload)
    assert status == 200 and json.loads(body) == {'message': 'Hello Juan Perez your message will be sent'}, f'Contrato: {status}'
    assert request('/DevOps', headers, payload)[0] == 409, 'La reutilización debe rechazarse'
    print('Emisor verificado: sin credencial 401, JWT nuevos, contrato 200 y reutilización 409.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    check(args.url, args.local)
