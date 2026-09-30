#!/usr/bin/env bash
set -euo pipefail
: "${DEPLOY_ENV:?}" "${IMAGE:?}"
# Los secretos se transmiten por la entrada estándar y no se imprimen.
python3 scripts/deploy.py
kubectl -n "devops-$DEPLOY_ENV" rollout status statefulset/redis --timeout=180s
kubectl -n "devops-$DEPLOY_ENV" rollout status deployment/devops-api --timeout=180s
kubectl -n "devops-$DEPLOY_ENV" rollout status deployment/kong --timeout=180s
# Cada transacción de prueba utiliza un JWT nuevo.
python3 scripts/smoke.py "$PUBLIC_URL"
