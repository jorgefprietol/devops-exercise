"""Un despliegue local debe terminar sin túnel público ni archivo de URLs."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import local_deploy_agent as agent


class LocalDeploymentTests(unittest.TestCase):
    def test_solicitud_de_un_pipeline_cancelado_no_se_despliega(self):
        item = {'creator': {'login': 'github-actions[bot]'}, 'environment': 'production',
                'payload': {'image': 'ghcr.io/jorgefprietol/devops-exercise@sha256:' + 'b' * 64, 'run_id': 1}}
        with patch.object(agent, 'gh', return_value={'status': 'completed', 'conclusion': 'cancelled'}), \
             patch.object(agent.subprocess, 'run') as run:
            self.assertFalse(agent.validate(item))
            run.assert_not_called()

    def test_despliegue_valida_el_cluster_sin_publicar_una_url(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as package:
            package.writestr('scripts/deploy.py', '# archivo de prueba')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / '.local'
            private.mkdir()
            (private / 'tls.crt').write_text('certificado')
            (private / 'tls.key').write_text('clave')
            item = {'sha': 'a' * 40, 'environment': 'production',
                    'payload': {'image': 'registry.example/api@sha256:' + 'b' * 64}}
            with patch.object(agent, 'ROOT', root), patch.object(agent, 'PRIVATE', private), \
                 patch.object(agent, 'credentials', return_value={'JWT_SECRET': 's' * 32}), \
                 patch.object(agent.subprocess, 'check_output', return_value=archive.getvalue()), \
                 patch.object(agent.subprocess, 'run') as run, \
                 patch.object(agent, 'verify_cluster', create=True, return_value={'resultado': 'correcto'}) as verify:
                agent.deploy(item)
                verify.assert_called_once()
                commands = [call.args[0] for call in run.call_args_list]
                self.assertFalse(any('public_tunnel.py' in str(command) for command in commands))
                self.assertFalse((private / 'public_urls.json').exists())


if __name__ == '__main__':
    unittest.main()
