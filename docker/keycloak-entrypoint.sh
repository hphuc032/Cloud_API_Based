#!/bin/bash
set -euo pipefail
case "${KC_HOSTNAME:-}" in
  https://*) ;;
  *) echo "Identity hostname must be a stable HTTPS origin" >&2; exit 1 ;;
esac
export KC_BOOTSTRAP_ADMIN_PASSWORD="$(cat /run/secrets/keycloak_admin_password)"
export KC_DB_PASSWORD="$(cat /run/secrets/identity_db_password)"
exec /opt/keycloak/bin/kc.sh start --import-realm
