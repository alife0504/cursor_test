#!/bin/bash
# scripts/generate_self_signed_cert.sh
#
# Phase 19 — 產生 self-signed TLS 憑證（開發/Staging 用）。
# Prod 請改用 Let's Encrypt（certbot），詳見 docs/runbooks/prod_deployment.md。
#
# 用法：
#   bash scripts/generate_self_signed_cert.sh
#   bash scripts/generate_self_signed_cert.sh tradingagents.local
#
# 輸出：
#   docker/nginx/certs/fullchain.pem
#   docker/nginx/certs/privkey.pem

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTS_DIR="${PROJECT_ROOT}/docker/nginx/certs"
CN="${1:-tradingagents.local}"
DAYS=365

mkdir -p "$CERTS_DIR"

if [ -f "$CERTS_DIR/fullchain.pem" ] && [ -f "$CERTS_DIR/privkey.pem" ]; then
    # 若 cert 還有效（剩 > 30 天），跳過
    if openssl x509 -in "$CERTS_DIR/fullchain.pem" -noout -checkend $((30*24*3600)) 2>/dev/null; then
        echo "✓ 既有 cert 還有效（剩 > 30 天），跳過產生。如需強制重產，先 rm certs/*.pem"
        exit 0
    fi
    echo "⚠ 既有 cert 將過期或已過期，重新產生..."
fi

# OpenSSL 配置（含 SAN — 必要否則新版瀏覽器不收）
TMP_CONF="$(mktemp)"
trap 'rm -f "$TMP_CONF"' EXIT

cat > "$TMP_CONF" <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C  = TW
ST = Taiwan
L  = Taipei
O  = TradingAgents-TW
OU = Dev
CN = ${CN}

[v3_req]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${CN}
DNS.2 = localhost
DNS.3 = *.${CN}
IP.1  = 127.0.0.1
IP.2  = ::1
EOF

openssl req \
    -x509 \
    -nodes \
    -days "$DAYS" \
    -newkey rsa:2048 \
    -keyout "$CERTS_DIR/privkey.pem" \
    -out "$CERTS_DIR/fullchain.pem" \
    -config "$TMP_CONF" \
    -extensions v3_req \
    2>/dev/null

chmod 600 "$CERTS_DIR/privkey.pem"
chmod 644 "$CERTS_DIR/fullchain.pem"

echo "✅ self-signed cert 已產生："
echo "   $CERTS_DIR/fullchain.pem"
echo "   $CERTS_DIR/privkey.pem"
echo ""
echo "有效期：$DAYS 天，CN=${CN}"
echo "後續 docker compose up 即可生效。"
