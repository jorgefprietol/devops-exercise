"""Contratos de infraestructura para almacenamiento y entrada de una nube."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from deploy import resources


class DeploymentPortabilityTests(unittest.TestCase):
    def settings(self, **extra):
        return patch.dict(os.environ, {
            'API_KEY': 'clave-de-prueba', 'JWT_SECRET': 'j' * 32,
            'REDIS_PASSWORD': 'a' * 48, 'TLS_CRT_B64': 'Y2VydA==', 'TLS_KEY_B64': 'a2V5',
            **extra}, clear=True)

    def manifest(self, kind, name):
        return next(item for item in resources('production', 'registry.example/api@sha256:' + 'a' * 64)
                    if item['kind'] == kind and item['metadata']['name'] == name)

    def test_volumen_usa_la_clase_de_almacenamiento_del_proveedor(self):
        for storage in ('gp3', 'managed-csi'):
            with self.subTest(storage=storage), self.settings(STORAGE_CLASS=storage):
                pvc = self.manifest('StatefulSet', 'redis')['spec']['volumeClaimTemplates'][0]
                self.assertEqual(storage, pvc['spec'].get('storageClassName'))

    def test_balanceador_conserva_la_configuracion_explicita_de_aws(self):
        annotations = {'service.beta.kubernetes.io/aws-load-balancer-scheme': 'internet-facing'}
        with self.settings(LOAD_BALANCER_CLASS='service.k8s.aws/nlb',
                           LOAD_BALANCER_ANNOTATIONS=json.dumps(annotations)):
            service = self.manifest('Service', 'kong')
            self.assertEqual('service.k8s.aws/nlb', service['spec'].get('loadBalancerClass'))
            self.assertEqual(annotations, service['metadata'].get('annotations'))
            self.assertEqual(8443, service['spec']['ports'][0]['targetPort'])

    def test_anotaciones_invalidas_se_rechazan_antes_de_desplegar(self):
        for value in ('[]', '{"clave": 4}', 'no-es-json'):
            with self.subTest(value=value), self.settings(LOAD_BALANCER_ANNOTATIONS=value):
                with self.assertRaises(ValueError):
                    self.manifest('Service', 'kong')

    def test_kind_no_hereda_opciones_del_balanceador_cloud(self):
        with self.settings(LAB_MODE='kind', LOAD_BALANCER_CLASS='service.k8s.aws/nlb',
                           LOAD_BALANCER_ANNOTATIONS='{"cloud":"valor"}'):
            service = self.manifest('Service', 'kong')
            self.assertEqual('NodePort', service['spec']['type'])
            self.assertNotIn('loadBalancerClass', service['spec'])
            self.assertNotIn('annotations', service['metadata'])


if __name__ == '__main__':
    unittest.main()
