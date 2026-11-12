set -Eeuo pipefail

provision_app() {
    local app="$1"
    local db_user_var="${app}_DB_USER"
    local db_name="$2"
    local password_file="/run/secrets/${app,,}_db_password"

    local db_user="${!db_user_var:?Missing $db_user_var}"

    if [[ ! -r "$password_file" ]]; then
        echo "Missing secret: $password_file" >&2
        return 1
    fi

    local db_password
    db_password="$(<"$password_file")"

    echo "Provisioning database: $db_name (user: $db_user)"

    psql -X -v ON_ERROR_STOP=1 \
        -v app_user="$db_user" \
        -v app_password="$db_password" \
        -v app_db="$db_name" \
        -f /provisioning/provision.sql
}

provision_app "LITELLM" "litellm"
provision_app "NEW_API" "new-api"
provision_app "GRAFANA" "grafana"
provision_app "HUB" "hub"

echo "Database provisioning completed."
