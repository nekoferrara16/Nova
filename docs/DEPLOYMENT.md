# Hosting a shared novaFinance instance

The application supports independent users with scoped accounts, transactions, budgets, import drafts, and exports. The default launcher binds only to your own computer. This repository does not provision or publish an online service.

## Configuration

| Variable | Default | Online setting |
| --- | --- | --- |
| `NOVA_DB` | `data/nova.sqlite3` under the repository | Absolute path on persistent storage |
| `NOVA_ALLOWED_HOSTS` | `127.0.0.1,localhost,testserver` | Your exact hostname, e.g. `finance.example.com` |
| `NOVA_PUBLIC_ORIGIN` | Request origin | Full public HTTPS origin, e.g. `https://finance.example.com` (no trailing slash) |
| `NOVA_SECURE_COOKIES` | `0` | `1` |
| `NOVA_ALLOW_REGISTRATION` | `1` | `0` to close registration after creating intended users |

Configuration comes from process environment variables; `.env` files are not automatically loaded.

## Deployment topology

Run one application instance behind an HTTPS reverse proxy. Terminate TLS at the proxy, preserve the public Host header, and proxy only to the private application port. The supplied container disables proxy-header trust; do not trust forwarded headers from arbitrary clients. If you enable them, restrict trusted proxy IPs explicitly in Uvicorn. Authentication attempts otherwise share the proxy's IP-based limit (30 attempts per 15 minutes), so configure rate limiting at the proxy as well.

```text
Browser → HTTPS reverse proxy → novaFinance → persistent SQLite volume
```

Example container launch, with HTTPS provided separately:

```sh
docker build -t novafinance .
docker volume create nova-data
docker run -d --name novafinance --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v nova-data:/data \
  -e NOVA_ALLOWED_HOSTS=finance.example.com \
  -e NOVA_PUBLIC_ORIGIN=https://finance.example.com \
  -e NOVA_SECURE_COOKIES=1 \
  -e NOVA_ALLOW_REGISTRATION=1 \
  novafinance
```

The image runs as an unprivileged user. A bind-mounted directory must be writable by that user. The container recipe is provided for deployment preparation; it has not been built or hosted as part of the local rebuild.

## Operations

- Keep the database on a local persistent disk, not an ephemeral container filesystem or a live network/cloud-sync folder. SQLite is suited to a modest personal/shared installation. Use PostgreSQL and migrations before scaling to multiple hosts or significant write concurrency.
- Put encrypted, tested backups in place. Stop the service before copying the SQLite database, or use SQLite's online backup API. A JSON export is portable user data; there is no JSON restore endpoint.
- Enable HTTPS, set the cookie/origin/host settings, and test two separate users before sharing access. Set `NOVA_ALLOW_REGISTRATION=0` once intended accounts exist if this is a private service.
- Passwords use salted PBKDF2-SHA256 with 600,000 iterations. Sessions expire after 12 hours and are stored as token hashes, with HttpOnly/SameSite cookies and CSRF checks on authenticated mutations. Use encrypted host storage for the database; it is not encrypted by this application.
- Password recovery, password change, MFA, email verification, invitations, account deletion, administration, and audit logs are not implemented. These are remaining requirements for a broadly available public product.
- The runtime has no paid API dependency. Infrastructure, domains, backups, electricity, and operational work may still cost money; free online hosting is not guaranteed.
