#!/usr/bin/env bash
# Builds the web and deploys it to the Static Web App created by the
# html-viewer-api repo (infra/).
#
# Requires: az (logged in), node 20+.
# Env:
#   RESOURCE_GROUP   resource group that holds the Static Web App
#   SWA_NAME         optional, defaults to the only Static Web App in the group
#   TENANT_ID        optional, defaults to the current az account tenant
set -euo pipefail

: "${RESOURCE_GROUP:?Set RESOURCE_GROUP}"
SWA_NAME="${SWA_NAME:-$(az staticwebapp list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv)}"
: "${SWA_NAME:?No Static Web App found in $RESOURCE_GROUP; deploy html-viewer-api first or set SWA_NAME}"
TENANT_ID="${TENANT_ID:-$(az account show --query tenantId -o tsv)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Web"
(
  cd "$ROOT"
  npm ci
  npm run build
  # Restrict sign-in to your tenant.
  sed -i.bak "s/__TENANT_ID__/$TENANT_ID/" dist/staticwebapp.config.json && rm dist/staticwebapp.config.json.bak
)
DEPLOY_TOKEN="$(az staticwebapp secrets list --name "$SWA_NAME" --resource-group "$RESOURCE_GROUP" --query properties.apiKey -o tsv)"
npx --yes @azure/static-web-apps-cli deploy "$ROOT/dist" --deployment-token "$DEPLOY_TOKEN" --env production

echo
echo "Listo: https://$(az staticwebapp show --name "$SWA_NAME" --resource-group "$RESOURCE_GROUP" --query defaultHostname -o tsv)"
