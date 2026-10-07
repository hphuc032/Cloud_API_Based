#!/bin/bash
set -euo pipefail
export KC_BOOTSTRAP_ADMIN_PASSWORD="$(cat /run/secrets/keycloak_admin_password)"
exec /opt/keycloak/bin/kc.sh start-dev
