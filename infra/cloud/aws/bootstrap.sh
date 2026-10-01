#!/bin/bash
# CloudFormation sustituye REGION, TOKEN_PARAMETER, NODE_ROLE y SERVER_IP.
set -euo pipefail
umask 077
export AWS_DEFAULT_REGION='__REGION__'
export TOKEN_PARAMETER='__TOKEN_PARAMETER__'
export NODE_ROLE='__NODE_ROLE__'
export SERVER_IP='__SERVER_IP__'
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl ca-certificates python3 python3-boto3 python3-venv unzip
install -d -m 700 /etc/rancher/k3s /opt/devops
python3 - <<'PY'
import os, secrets, time, pathlib, boto3
client = boto3.client('ssm', region_name=os.environ['AWS_DEFAULT_REGION'])
parameter = os.environ['TOKEN_PARAMETER']
if os.environ['NODE_ROLE'] == 'server':
    token = secrets.token_hex(32)
    client.put_parameter(Name=parameter, Value=token, Type='SecureString', Overwrite=True)
    config = 'disable:\n  - traefik\nsecrets-encryption: true\nwrite-kubeconfig-mode: "0600"\n'
else:
    for attempt in range(90):
        try:
            token = client.get_parameter(Name=parameter, WithDecryption=True)['Parameter']['Value']
            break
        except client.exceptions.ParameterNotFound:
            time.sleep(10)
    else:
        raise RuntimeError('El servidor no publico el token de union')
    config = 'server: https://' + os.environ['SERVER_IP'] + ':6443\n'
pathlib.Path('/etc/rancher/k3s/config.yaml').write_text(config + 'token: "' + token + '"\n')
PY
VERSION='v1.34.12+k3s1'
curl --fail --location --retry 4 "https://github.com/k3s-io/k3s/releases/download/$VERSION/k3s" -o /usr/local/bin/k3s
curl --fail --location --retry 4 "https://github.com/k3s-io/k3s/releases/download/$VERSION/sha256sum-amd64.txt" -o /opt/devops/k3s.sha256
(cd /usr/local/bin && grep ' k3s$' /opt/devops/k3s.sha256 | sha256sum --check --strict)
chmod 755 /usr/local/bin/k3s
curl --fail --location --retry 4 "https://raw.githubusercontent.com/k3s-io/k3s/$VERSION/install.sh" -o /opt/devops/install-k3s.sh
INSTALL_K3S_SKIP_DOWNLOAD=true INSTALL_K3S_EXEC="$NODE_ROLE" sh /opt/devops/install-k3s.sh
if [ "$NODE_ROLE" = server ]; then
    python3 -m venv /opt/devops/certbot
    /opt/devops/certbot/bin/pip install --disable-pip-version-check 'certbot==5.4.0'
fi
touch /opt/devops/bootstrap-completo
