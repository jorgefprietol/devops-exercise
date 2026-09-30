"""Instala las versiones fijadas de red y métricas en el cluster de laboratorio."""
from pathlib import Path
import datetime
import ipaddress
import os
import subprocess
import urllib.request
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

root = Path(__file__).resolve().parents[1]
private = root / '.local'
env = os.environ.copy()
env['KUBECONFIG'] = str(private / 'kubeconfig')

calico = urllib.request.urlopen('https://raw.githubusercontent.com/projectcalico/calico/v3.32.2/manifests/calico.yaml').read().decode()
calico = calico.replace('# - name: CALICO_IPV4POOL_CIDR\n            #   value: "192.168.0.0/16"', '- name: CALICO_IPV4POOL_CIDR\n              value: "10.244.0.0/16"')
objects = list(yaml.safe_load_all(calico))
for item in objects:
    if item and item['kind'] == 'DaemonSet':
        # Los nodos de kind en Docker Desktop no exponen securityfs.
        # En este entorno se utiliza el plano de datos iptables de Calico.
        spec = item['spec']['template']['spec']
        spec['volumes'] = [v for v in spec['volumes'] if v['name'] != 'sys-kernel-security']
        for container in item['spec']['template']['spec']['containers']:
            if container['name'] == 'calico-node':
                container['volumeMounts'] = [v for v in container['volumeMounts'] if v['name'] != 'sys-kernel-security']
                entries = container['env']
                entries[:] = [e for e in entries if e['name'] not in ('CALICO_IPV4POOL_CIDR', 'CALICO_IPV4POOL_IPIP', 'CALICO_IPV4POOL_VXLAN')]
                entries += [{'name':'CALICO_IPV4POOL_CIDR','value':'10.244.0.0/16'}, {'name':'CALICO_IPV4POOL_IPIP','value':'Never'}, {'name':'CALICO_IPV4POOL_VXLAN','value':'Always'}]
subprocess.run(['kubectl','apply','--server-side','-f','-'], input=yaml.safe_dump_all(objects), text=True, env=env, check=True)
metrics = urllib.request.urlopen('https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.9.0/components.yaml').read().decode()
objects = list(yaml.safe_load_all(metrics))
for item in objects:
    if item and item['kind'] == 'Deployment':
        item['spec']['template']['spec']['containers'][0]['args'].append('--kubelet-insecure-tls')
subprocess.run(['kubectl','apply','-f','-'], input=yaml.safe_dump_all(objects), text=True, env=env, check=True)

if not (private / 'tls.crt').exists():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).sign(key,hashes.SHA256()))
    (private/'tls.crt').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (private/'tls.key').write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
print('Calico, Metrics Server y TLS local preparados. La excepción TLS de kubelet solo corresponde a este laboratorio.')
