#!/bin/sh
# Redeploy a git-backed Portainer stack, pulling the new image.
# Replaces cssnr/portainer-stack-deploy-action from the GitHub workflows.
#
# Usage: portainer-redeploy.sh <stack-name> <env-json-array>
#   <stack-name>       Portainer stack name (e.g. $BACKEND_DEPLOYMENT_SERVICE)
#   <env-json-array>   JSON array of {name,value} objects (built with jq)
#
# Requires env: PORTAINER_URL, PORTAINER_TOKEN. Needs curl + jq.
# NOTE: best-effort port — verify the endpoints against your Portainer version.
# The stack must already exist (create it once in Portainer); this only
# redeploys it. The env array REPLACES the stack env, so it must be complete.
set -eu

STACK_NAME="$1"
ENV_ARRAY="$2"

STACKS=$(curl -sf -H "X-API-Key: $PORTAINER_TOKEN" "$PORTAINER_URL/api/stacks")
STACK_ID=$(echo "$STACKS" | jq -r --arg n "$STACK_NAME" '.[] | select(.Name==$n) | .Id')
ENDPOINT_ID=$(echo "$STACKS" | jq -r --arg n "$STACK_NAME" '.[] | select(.Name==$n) | .EndpointId')

if [ -z "$STACK_ID" ] || [ "$STACK_ID" = "null" ]; then
  echo "ERROR: stack '$STACK_NAME' not found in Portainer" >&2
  exit 1
fi

echo "Redeploying stack '$STACK_NAME' (id=$STACK_ID, endpoint=$ENDPOINT_ID)"
curl -sf -X PUT \
  -H "X-API-Key: $PORTAINER_TOKEN" \
  -H "Content-Type: application/json" \
  "$PORTAINER_URL/api/stacks/$STACK_ID/git/redeploy?endpointId=$ENDPOINT_ID" \
  --data "$(jq -n --argjson env "$ENV_ARRAY" '{env: $env, pullImage: true, prune: true}')" \
  >/dev/null
echo "Deploy request sent for '$STACK_NAME'."
