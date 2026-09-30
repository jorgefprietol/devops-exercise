"""End-to-end contract checks through Kong. --local allows only localhost TLS demo."""
import argparse
import base64
import hashlib
import hmac
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor


def token():
    def enc(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).rstrip(b'=')
    now = int(time.time())
    body = enc({'alg': 'HS256', 'typ': 'JWT'}) + b'.' + enc({
        'iss': 'devops-candidate', 'aud': 'devops-api', 'sub': 'smoke-test',
        'iat': now, 'nbf': now, 'exp': now + 300, 'jti': uuid.uuid4().hex})
    sig = base64.urlsafe_b64encode(hmac.new(os.environ['JWT_SECRET'].encode(), body, hashlib.sha256).digest()).rstrip(b'=')
    return (body + b'.' + sig).decode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.url)
    if parsed.scheme != 'https' or (args.local and parsed.hostname not in ('localhost', '127.0.0.1')):
        raise SystemExit('Use HTTPS; --local is restricted to localhost.')
    ctx = ssl._create_unverified_context() if args.local else ssl.create_default_context()
    def send(method='POST', jwt=None, api_key=None):
        data = json.dumps({'message': 'This is a test', 'to': 'Juan Perez', 'from': 'Rita Asturia', 'timeToLifeSec': 45}).encode()
        req = urllib.request.Request(args.url.rstrip('/') + '/DevOps',
            data=data if method == 'POST' else None, method=method,
            headers={'Content-Type': 'application/json', 'X-Parse-REST-API-Key': api_key or os.environ['API_KEY'], 'X-JWT-KWY': jwt or token()})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as res:
                return res.status, res.read().decode()
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode()
    jwt = token()
    status, body = send(jwt=jwt)
    assert status == 200 and json.loads(body) == {'message': 'Hello Juan Perez your message will be sent'}, (status, body)
    assert send(jwt=jwt)[0] == 409, 'Replay must be rejected across replicas'
    for method in ('GET', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'):
        assert send(method) == (405, 'ERROR'), method
    assert send('HEAD') == (405, '')
    assert send(api_key='wrong')[0] in (401, 403)
    assert send(jwt='invalid')[0] == 401
    jwt = token()
    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(lambda _: send(jwt=jwt)[0], range(10)))
    assert statuses.count(200) == 1 and statuses.count(409) == 9, statuses
    print('PASS: exact contract, methods, authentication and concurrent replay through gateway.')


if __name__ == '__main__':
    main()
