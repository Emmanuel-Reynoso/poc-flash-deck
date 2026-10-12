#!/usr/bin/env bash
# Deploys infra (Bicep) and the API (Functions). The web is deployed from the
# html-viewer-web repo, into the Static Web App created here.
#
# Requires: az (logged in), func (Core Tools v4), jq.
# Env:
#   RESOURCE_GROUP        target resource group (created if missing)
#   LOCATION              region for the resource group (default: eastus2)
#   ENTRA_CLIENT_ID       app registration client id (see README)
#   ENTRA_CLIENT_SECRET   app registration client secret
set -euo pipefail

: "${RESOURCE_GROUP:?Set RESOURCE_GROUP}"
: "${ENTRA_CLIENT_ID:?Set ENTRA_CLIENT_ID}"
: "${ENTRA_CLIENT_SECRET:?Set ENTRA_CLIENT_SECRET}"
LOCATION="${LOCATION:-eastus2}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Infrastructure"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
outputs="$(az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name html-viewer \
  --template-file "$ROOT/infra/main.bicep" \
  --parameters "$ROOT/infra/main.bicepparam" \
  --query properties.outputs --output json)"

FUNC_APP="$(jq -r .functionAppName.value <<<"$outputs")"
SWA_NAME="$(jq -r .staticWebAppName.value <<<"$outputs")"
WEB_URL="$(jq -r .webUrl.value <<<"$outputs")"
REDIRECT_URI="$(jq -r .entraRedirectUri.value <<<"$outputs")"

echo "==> Entra ID redirect URI"
az ad app update --id "$ENTRA_CLIENT_ID" --web-redirect-uris "$REDIRECT_URI" --enable-id-token-issuance true

echo "==> API"
(cd "$ROOT" && func azure functionapp publish "$FUNC_APP" --python)

echo
echo "Listo: API publicada en $FUNC_APP"
echo "Static Web App: $SWA_NAME ($WEB_URL)"
echo "Para publicar la web, en html-viewer-web:"
echo "  RESOURCE_GROUP=$RESOURCE_GROUP SWA_NAME=$SWA_NAME ./scripts/deploy.sh"
