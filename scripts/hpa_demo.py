"""Bounded synthetic CPU test, not a traffic throughput benchmark."""
from pathlib import Path
import json
import os
import subprocess
import time

root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env['KUBECONFIG'] = str(root / '.local/kubeconfig')
base = ['kubectl', '-n', 'devops-production']
def get(kind):
    return json.loads(subprocess.check_output(base + ['get'] + kind + ['-o','json'], env=env))

pod = get(['pods','-l','app=devops-api'])['items'][0]['metadata']['name']
before = get(['hpa','devops-api'])['status'].get('currentReplicas', 0)
# The timed loop is confined to one application container in this dedicated lab.
command = 'end=$(( $(date +%s) + 90 )); while [ $(date +%s) -lt "$end" ]; do :; done'
load = subprocess.Popen(base + ['exec',pod,'--','sh','-c',command], env=env, stdout=subprocess.DEVNULL)
records = []
for _ in range(14):
    hpa = get(['hpa','devops-api'])
    status = hpa.get('status', {})
    available = get(['deployment','devops-api']).get('status',{}).get('availableReplicas',0)
    record = {'time': time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), 'current': status.get('currentReplicas'), 'desired': status.get('desiredReplicas'), 'available':available, 'metrics': status.get('currentMetrics')}
    records.append(record)
    print(json.dumps(record), flush=True)
    time.sleep(10)
load.wait(timeout=10)
assert any((x.get('desired') or 0) > before for x in records), 'HPA did not request more replicas'
assert any((x.get('current') or 0) > before for x in records), 'New replicas were not observed'
assert any(x['available'] > before for x in records), 'Additional replicas did not become available'
(root/'evidence/hpa-live.json').write_text(json.dumps({'test':'90-second synthetic CPU load in one API pod; not an HTTP throughput benchmark','initial':before,'records':records},indent=2),encoding='utf-8')
print('PASS: HPA increased replicas from its initial value. CPU load has ended.',flush=True)
