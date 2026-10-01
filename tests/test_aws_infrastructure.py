"""Verifica límites de exposición y eliminación del laboratorio facturable."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from aws_template import template
from deploy import resources


class AwsInfrastructureTests(unittest.TestCase):
    def test_only_https_and_certificate_validation_are_public(self):
        items = template()['Resources']
        ingress = items['NodesSecurity']['Properties']['SecurityGroupIngress']
        self.assertEqual({rule['FromPort'] for rule in ingress}, {80, 443})
        for name in ('PrivateApi', 'PrivateKubelet', 'PrivateOverlay'):
            self.assertNotIn('CidrIp', items[name]['Properties'])
            self.assertIn('SourceSecurityGroupId', items[name]['Properties'])

    def test_expiry_deletes_only_the_two_bounded_instances(self):
        items = template()['Resources']
        for node in ('Server', 'Worker'):
            props = items[node]['Properties']
            self.assertEqual(props['CreditSpecification']['CPUCredits'], 'standard')
            self.assertEqual(props['MetadataOptions']['HttpTokens'], 'required')
            disk = props['BlockDeviceMappings'][0]['Ebs']
            self.assertTrue(disk['Encrypted'] and disk['DeleteOnTermination'])
        expiry = items['Expiry']['Properties']
        self.assertEqual(expiry['Target']['Input']['Fn::Sub'], '{"InstanceIds":["${Server}","${Worker}"]}')
        statements = items['ExpiryRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
        self.assertEqual(statements[0]['Action'], 'ec2:TerminateInstances')
        self.assertEqual(len(statements[0]['Resource']), 2)

    def test_nonproduction_can_use_private_gateway_without_new_load_balancer(self):
        env = {'API_KEY': 'demo', 'JWT_SECRET': 'x'*32, 'REDIS_PASSWORD': 'a'*64,
               'TLS_CRT_B64': 'YQ==', 'TLS_KEY_B64': 'Yg==', 'GATEWAY_SERVICE_TYPE': 'ClusterIP'}
        with patch.dict(os.environ, env, clear=True):
            items = resources('staging', 'ghcr.io/test/api@sha256:' + 'a'*64)
        gateway = next(i for i in items if i['kind'] == 'Service' and i['metadata']['name'] == 'kong')
        self.assertEqual(gateway['spec']['type'], 'ClusterIP')
        self.assertNotIn('nodePort', gateway['spec']['ports'][0])


if __name__ == '__main__':
    unittest.main()
