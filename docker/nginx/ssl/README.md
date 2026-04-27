# SSL certificates

Put nginx TLS certificate files in this directory when `ENABLE_SSL=true`.

Example `.env` values:

```env
ENABLE_SSL=true
SSL_CERT_FILE=server.crt
SSL_KEY_FILE=server.key
```

The files are mounted read-only into `/etc/nginx/ssl`.
