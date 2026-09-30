"""Comprueba que el control de dependencias falle ante riesgos o informes incompletos."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from dependency_audit import inspect


class DependencyAuditTests(unittest.TestCase):
    def test_informe_sin_vulnerabilidades(self):
        self.assertEqual([], inspect({'version': 1, 'projects': [{'path': 'api.csproj'}]}))

    def test_informe_incompleto_no_se_acepta(self):
        for report in ({}, {'version': 1, 'projects': []},
                       {'version': 1, 'projects': [{'path': 'api.csproj'}], 'problems': ['Sin conexión']},
                       {'version': 1, 'projects': [{'path': 'api.csproj', 'problems': ['Sin restaurar']}]}):
            with self.subTest(report=report), self.assertRaises(ValueError):
                inspect(report)

    def test_detecta_dependencias_directas_y_transitivas(self):
        issue = {'id': 'paquete-prueba', 'resolvedVersion': '1.0.0',
                 'vulnerabilities': [{'severity': 'High', 'advisoryurl': 'https://example.org/aviso'}]}
        for group in ('topLevelPackages', 'transitivePackages'):
            report = {'version': 1, 'projects': [{'frameworks': [{group: [issue]}]}]}
            with self.subTest(group=group):
                self.assertEqual([('paquete-prueba', '1.0.0', 'High', 'https://example.org/aviso')], inspect(report))


if __name__ == '__main__':
    unittest.main()
