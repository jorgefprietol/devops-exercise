"""Comprueba aislamiento y persistencia de las credenciales del laboratorio."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from environment_config import credentials, ENVIRONMENTS


class EnvironmentConfigTests(unittest.TestCase):
    def test_entornos_no_comparten_secretos_y_reinicio_no_los_rota(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = {env: credentials(root, env, create=True) for env in ENVIRONMENTS}
            for key in ('JWT_SECRET', 'REDIS_PASSWORD', 'ISSUER_KEY'):
                self.assertEqual(3, len({value[key] for value in settings.values()}))
            for env in ENVIRONMENTS:
                self.assertEqual(settings[env], credentials(root, env, create=True))

    def test_entorno_desconocido_no_crea_archivos(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                credentials(root, '../../ajeno', create=True)
            self.assertEqual([], list(root.iterdir()))

    def test_agente_no_inventa_credenciales_si_falta_configuracion(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                credentials(Path(folder), 'staging')


if __name__ == '__main__':
    unittest.main()
