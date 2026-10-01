"""El emisor entrega tokens individuales y conserva privada la clave de firma."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from issue_jwt import issue


class IssueJwtTests(unittest.TestCase):
    def test_tokens_distintos_firmados_y_con_vigencia_limitada(self):
        secret = 'firma-de-prueba-' * 4
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('API_KEY=prueba\nJWT_SECRET=' + secret + '\nREDIS_PASSWORD=prueba\n')
            first, second = issue(root, 'production'), issue(root, 'production')
        claims = []
        for token in (first, second):
            header, body, signature = token.split('.')
            expected = hmac.new(secret.encode(), (header + '.' + body).encode(), hashlib.sha256).digest()
            self.assertEqual(expected, base64.urlsafe_b64decode(signature + '=='))
            payload = json.loads(base64.urlsafe_b64decode(body + '=='))
            self.assertEqual(('devops-candidate', 'devops-api'), (payload['iss'], payload['aud']))
            self.assertEqual(300, payload['exp'] - payload['iat'])
            self.assertGreater(payload['exp'], time.time())
            self.assertNotIn(secret, token)
            claims.append(payload)
        self.assertNotEqual(claims[0]['jti'], claims[1]['jti'])

    def test_no_crea_secretos_si_el_entorno_no_esta_preparado(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                issue(root, 'production')
            self.assertEqual([], list(root.iterdir()))

    def test_no_utiliza_credenciales_de_otro_entorno(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('API_KEY=prueba\nJWT_SECRET=' + 's' * 32 + '\nREDIS_PASSWORD=prueba\n')
            with self.assertRaises(FileNotFoundError):
                issue(root, 'staging')

    def test_archivo_cloud_explicito_no_usa_la_firma_local(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cloud = root / 'cloud.env'
            cloud.write_text('JWT_SECRET=' + 'c' * 32 + '\n')
            encoded = issue(root, 'production', cloud)
            header, body, signature = encoded.split('.')
            expected = hmac.new(('c' * 32).encode(), (header + '.' + body).encode(), hashlib.sha256).digest()
            self.assertEqual(expected, base64.urlsafe_b64decode(signature + '=='))
            self.assertFalse((root / '.env').exists())


if __name__ == '__main__':
    unittest.main()
