"""Portable Kubernetes infrastructure, versioned as Python-generated JSON.
Requires an existing Kubernetes >=1.30 cluster, two workers, Metrics Server,
default StorageClass and LoadBalancer implementation. No cloud account is created.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
from kong_config import config


def resources(env, image):
    if env not in ('development', 'staging', 'production'):
        raise ValueError('Invalid environment')
    if not re.fullmatch(r'[a-z0-9./_-]+@sha256:[a-f0-9]{64}', image):
        raise ValueError('Deploy an immutable image digest')
    ns = 'devops-' + env
    def obj(kind, name, spec=None, api='v1', **extra):
        value = {'apiVersion': api, 'kind': kind, 'metadata': {'name': name, 'namespace': ns}, **extra}
        if spec is not None:
            value['spec'] = spec
        return value
    def envvar(name, value): return {'name': name, 'value': value}
    def secretvar(name, key): return {'name': name, 'valueFrom': {'secretKeyRef': {'name': 'app-secrets', 'key': key}}}
    def limits(cpu, memory): return {'requests': {'cpu': cpu, 'memory': memory}, 'limits': {'cpu': '1', 'memory': '512Mi'}}
    def probe(path, port): return {'httpGet': {'path': path, 'port': port}, 'initialDelaySeconds': 5, 'periodSeconds': 5}
    def spread(label):
        return [{'maxSkew': 1, 'minDomains': 2, 'topologyKey': 'kubernetes.io/hostname',
                 'nodeTaintsPolicy': 'Honor',
                 'whenUnsatisfiable': 'DoNotSchedule', 'labelSelector': {'matchLabels': {'app': label}}}]
    security = {'runAsNonRoot': True, 'allowPrivilegeEscalation': False,
                'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}}
    signer = os.environ['JWT_SECRET']
    if len(signer.encode()) < 32:
        raise ValueError('JWT_SECRET must contain at least 32 bytes')
    redis_password = os.environ['REDIS_PASSWORD']
    if not re.fullmatch(r'[a-fA-F0-9]{32,128}', redis_password):
        raise ValueError('Use a random hex Redis password of 32 to 128 characters')
    kong = json.dumps(config())
    stamp = hashlib.sha256((kong + redis_password).encode()).hexdigest()
    tls = {'tls.crt': os.environ['TLS_CRT_B64'], 'tls.key': os.environ['TLS_KEY_B64']}
    for value in tls.values(): base64.b64decode(value, validate=True)
    result = [
        {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': ns}},
        obj('Secret', 'app-secrets', stringData={'API_KEY': os.environ['API_KEY'], 'JWT_SECRET': signer,
            'REDIS_PASSWORD': redis_password,
            'REDIS_CONNECTION': 'redis:6379,password=' + redis_password + ',abortConnect=false'}),
        obj('Secret', 'kong-config', stringData={'kong.json': kong}),
        obj('Secret', 'gateway-tls', type='kubernetes.io/tls', data=tls),
        obj('Service', 'redis', {'clusterIP': 'None', 'selector': {'app': 'redis'}, 'ports': [{'port': 6379}]}),
        obj('StatefulSet', 'redis', {
            'serviceName': 'redis', 'replicas': 1, 'selector': {'matchLabels': {'app': 'redis'}},
            'template': {'metadata': {'labels': {'app': 'redis'}, 'annotations': {'config-hash': stamp}},
              'spec': {'automountServiceAccountToken': False, 'securityContext': {'fsGroup': 999},
                'containers': [{'name': 'redis', 'image': 'redis:7.4-alpine',
                  'command': ['sh', '-c', 'exec redis-server --appendonly yes --appendfsync always --requirepass "$REDIS_PASSWORD"'],
                  'env': [secretvar('REDIS_PASSWORD', 'REDIS_PASSWORD')],
                  'ports': [{'containerPort': 6379}], 'resources': limits('100m', '128Mi'),
                  'readinessProbe': {'exec': {'command': ['sh','-c','REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli ping']}, 'periodSeconds': 5},
                  'volumeMounts': [{'name': 'data', 'mountPath': '/data'}]}]}},
            'volumeClaimTemplates': [{'metadata': {'name': 'data'}, 'spec': {'accessModes': ['ReadWriteOnce'],
                'resources': {'requests': {'storage': '1Gi'}}}}]}, api='apps/v1'),
        obj('Service', 'devops-api', {'selector': {'app': 'devops-api'}, 'ports': [{'port': 8080}]}),
        obj('Deployment', 'devops-api', {
            'replicas': 2, 'revisionHistoryLimit': 5, 'selector': {'matchLabels': {'app': 'devops-api'}},
            'strategy': {'type': 'RollingUpdate', 'rollingUpdate': {'maxSurge': 1, 'maxUnavailable': 0}},
            'template': {'metadata': {'labels': {'app': 'devops-api'}, 'annotations': {'config-hash': stamp}},
              'spec': {'automountServiceAccountToken': False, 'topologySpreadConstraints': spread('devops-api'),
                'containers': [{'name': 'api', 'image': image, 'securityContext': security,
                  'ports': [{'containerPort': 8080}], 'resources': limits('100m', '128Mi'),
                  'env': [secretvar(k, k) for k in ('API_KEY', 'JWT_SECRET', 'REDIS_CONNECTION')],
                  'livenessProbe': probe('/health/live', 8080), 'readinessProbe': probe('/health/ready', 8080)}]}}}, api='apps/v1'),
        obj('HorizontalPodAutoscaler', 'devops-api', {
            'scaleTargetRef': {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'name': 'devops-api'},
            'minReplicas': 2, 'maxReplicas': 6,
            'metrics': [{'type': 'Resource', 'resource': {'name': 'cpu', 'target': {'type': 'Utilization', 'averageUtilization': 65}}}],
            'behavior': {'scaleDown': {'stabilizationWindowSeconds': 120}}}, api='autoscaling/v2'),
        obj('PodDisruptionBudget', 'devops-api', {'minAvailable': 1, 'selector': {'matchLabels': {'app': 'devops-api'}}}, api='policy/v1'),
        obj('Deployment', 'kong', {
            'replicas': 2, 'selector': {'matchLabels': {'app': 'kong'}},
            'template': {'metadata': {'labels': {'app': 'kong'}, 'annotations': {'config-hash': stamp}},
              'spec': {'automountServiceAccountToken': False, 'topologySpreadConstraints': spread('kong'),
                'containers': [{'name': 'kong', 'image': 'kong:3.9', 'resources': limits('100m', '256Mi'),
                  'env': [envvar(k, v) for k, v in {
                      'KONG_DATABASE':'off', 'KONG_ADMIN_LISTEN':'off', 'KONG_PROXY_LISTEN':'0.0.0.0:8443 ssl',
                      'KONG_STATUS_LISTEN':'0.0.0.0:8100', 'KONG_DECLARATIVE_CONFIG':'/kong/kong.json',
                      'KONG_NGINX_WORKER_PROCESSES':'2',
                      'KONG_SSL_CERT':'/tls/tls.crt', 'KONG_SSL_CERT_KEY':'/tls/tls.key'}.items()],
                  'ports': [{'containerPort': 8443}], 'readinessProbe': probe('/status/ready', 8100),
                  'volumeMounts': [{'name':'config','mountPath':'/kong','readOnly':True}, {'name':'tls','mountPath':'/tls','readOnly':True}]}],
                'volumes': [{'name':'config','secret':{'secretName':'kong-config'}}, {'name':'tls','secret':{'secretName':'gateway-tls'}}]}}}, api='apps/v1'),
        obj('Service', 'kong', {'type': 'LoadBalancer', 'selector': {'app': 'kong'},
            'ports': [{'name': 'https', 'port': 443, 'targetPort': 8443}]}),
        obj('NetworkPolicy', 'api-only-from-kong', {'podSelector': {'matchLabels': {'app':'devops-api'}},
            'policyTypes': ['Ingress'], 'ingress': [{'from': [{'podSelector': {'matchLabels': {'app':'kong'}}}],
                'ports': [{'protocol':'TCP','port':8080}]}]}, api='networking.k8s.io/v1'),
        obj('NetworkPolicy', 'redis-only-from-api', {'podSelector': {'matchLabels': {'app':'redis'}},
            'policyTypes': ['Ingress'], 'ingress': [{'from': [{'podSelector': {'matchLabels': {'app':'devops-api'}}}],
                'ports': [{'protocol':'TCP','port':6379}]}]}, api='networking.k8s.io/v1')
    ]
    if os.environ.get('LAB_MODE') == 'kind':
        for item in result:
            if item['kind'] == 'Service' and item['metadata']['name'] == 'kong':
                item['spec']['type'] = 'NodePort'
                item['spec']['ports'][0]['nodePort'] = {'production': 30443, 'staging': 30444, 'development': 30445}[env]
    return result


if __name__ == '__main__':
    items = resources(os.environ['DEPLOY_ENV'], os.environ['IMAGE'])
    subprocess.run(['kubectl', 'apply', '-f', '-'], input=json.dumps({'apiVersion':'v1','kind':'List','items':items}), text=True, check=True)
