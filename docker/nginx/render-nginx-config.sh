#!/bin/sh
set -eu

write_server() {
  LISTEN_DIRECTIVE="$1"
  SSL_DIRECTIVES="${2:-}"

  cat >> /etc/nginx/conf.d/default.conf <<EOF
server {
  ${LISTEN_DIRECTIVE}
  server_name _;
${SSL_DIRECTIVES}

  client_max_body_size 50m;
  proxy_http_version 1.1;
  proxy_set_header Host \$host;
  proxy_set_header X-Real-IP \$remote_addr;
  proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto \$scheme;

  location = /api {
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_pass http://api_upstream;
  }

  location /api/ {
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_pass http://api_upstream;
  }

  location = /ws {
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_pass http://api_upstream;
  }

  location /ws/ {
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_pass http://api_upstream;
  }

  location / {
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_pass http://web_upstream;
  }
}

EOF
}

cat > /etc/nginx/conf.d/default.conf <<EOF
log_format proxy_main '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                      '\$status \$body_bytes_sent "\$http_referer" '
                      '"\$http_user_agent" "\$http_x_forwarded_for" '
                      'rt=\$request_time upstream=\$upstream_addr '
                      'ustatus=\$upstream_status urt=\$upstream_response_time';

access_log /var/log/nginx/access.log proxy_main;

map \$http_upgrade \$connection_upgrade {
  default upgrade;
  '' close;
}

upstream web_upstream {
  server web:3000;
}

upstream api_upstream {
  server api:8000;
}

EOF

write_server "listen 80;"

if [ "${ENABLE_SSL:-false}" = "true" ]; then
  CERT_FILE="${SSL_CERT_FILE:-server.crt}"
  KEY_FILE="${SSL_KEY_FILE:-server.key}"
  CERT_PATH="/etc/nginx/ssl/${CERT_FILE}"
  KEY_PATH="/etc/nginx/ssl/${KEY_FILE}"

  if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
    echo "SSL is enabled, but certificate or key file is missing." >&2
    echo "Expected certificate: $CERT_PATH" >&2
    echo "Expected key: $KEY_PATH" >&2
    exit 1
  fi

  SSL_DIRECTIVES="  ssl_certificate ${CERT_PATH};
  ssl_certificate_key ${KEY_PATH};
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_prefer_server_ciphers off;"
  write_server "listen 443 ssl;" "$SSL_DIRECTIVES"
fi

exec nginx -g "daemon off;"
