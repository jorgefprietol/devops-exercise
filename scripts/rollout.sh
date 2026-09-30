#!/usr/bin/env bash
set -euo pipefail
: "${DEPLOY_ENV:?}" "${IMAGE:?}"
# deploy.py sends secrets to kubectl stdin; never print its rendered secret objects.
python3 scripts/deploy.py
kubectl -n "devops-$DEPLOY_ENV" rollout status statefulset/redis --timeout=180s
kubectl -n "devops-$DEPLOY_ENV" rollout status deployment/devops-api --timeout=180s
kubectl -n "devops-$DEPLOY_ENV" rollout status deployment/kong --timeout=180s
# A fresh JWT is issued by the smoke client for each accepted transaction.
python3 scripts/smoke.py "$PUBLIC_URL"
