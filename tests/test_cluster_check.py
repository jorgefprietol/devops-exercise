"""La comprobación no debe aceptar un laboratorio sin distribución ni métricas."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cluster_check import gateway_forward, verify_cluster
import cluster_check


def pods(nodes):
    return {'items': [{'metadata': {}, 'spec': {'nodeName': node},
                      'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}} for node in nodes]}


class ClusterCheckTests(unittest.TestCase):
    def test_espera_un_error_temporal_del_gateway_con_jwt_nuevo(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = b'{"message":"Hello Juan Perez your message will be sent"}'
        temporary = urllib.error.HTTPError('https://127.0.0.1', 504, 'Gateway Timeout', {}, None)
        with patch('urllib.request.urlopen', side_effect=[temporary, response]) as send, \
             patch('cluster_check.time.sleep'):
            cluster_check.wait_gateway({'API_KEY': 'clave', 'JWT_SECRET': 's' * 32}, 'https://127.0.0.1:45678')
            self.assertEqual(2, send.call_count)
            tokens = [call.args[0].get_header('X-jwt-kwy') for call in send.call_args_list]
            self.assertTrue(all(tokens))
            self.assertNotEqual(tokens[0], tokens[1])

    def test_no_reintenta_credenciales_incorrectas(self):
        unauthorized = urllib.error.HTTPError('https://127.0.0.1', 401, 'Unauthorized', {}, None)
        with patch('urllib.request.urlopen', side_effect=unauthorized) as send:
            with self.assertRaises(urllib.error.HTTPError):
                cluster_check.wait_gateway({'API_KEY': 'clave', 'JWT_SECRET': 's' * 32}, 'https://127.0.0.1:45678')
            send.assert_called_once()

    def test_dos_pods_en_un_solo_nodo_no_cumplen(self):
        with patch('cluster_check.subprocess.check_output', return_value=json.dumps(pods(['nodo-1', 'nodo-1'])).encode()):
            with self.assertRaisesRegex(RuntimeError, 'dos nodos'):
                verify_cluster(Path('.'), {}, 'devops-production')

    def test_no_acepta_hpa_sin_metricas(self):
        def response(command, **kwargs):
            if 'pods' in command:
                return json.dumps(pods(['nodo-1', 'nodo-2'])).encode()
            return b'{"status":{"conditions":[{"type":"ScalingActive","status":"False"}]}}'
        with patch('cluster_check.subprocess.check_output', side_effect=response), patch('cluster_check.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'métricas'):
                verify_cluster(Path('.'), {}, 'devops-production')

    def test_port_forward_rechaza_namespace_ajeno(self):
        with self.assertRaises(ValueError), gateway_forward({}, 'kube-system'):
            self.fail('No debe abrir el puerto')

    def test_port_forward_se_cierra_incluso_si_la_prueba_falla(self):
        def start(command, **kwargs):
            self.assertIn('--address=127.0.0.1', command)
            self.assertIn(':443', command)
            kwargs['stdout'].write(b'Forwarding from 127.0.0.1:45678 -> 8443\n')
            kwargs['stdout'].flush()
            return process
        with patch('cluster_check.subprocess.Popen') as popen:
            process = popen.return_value
            process.poll.return_value = None
            popen.side_effect = start
            with self.assertRaisesRegex(RuntimeError, 'fallo de prueba'):
                with gateway_forward({}, 'devops-production') as url:
                    self.assertEqual('https://127.0.0.1:45678', url)
                    raise RuntimeError('fallo de prueba')
            process.terminate.assert_called_once()
            process.wait.assert_called_once()


if __name__ == '__main__':
    unittest.main()
