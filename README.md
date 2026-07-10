# dmarc-all-you-need

Minimal, beautiful, self-hostable DMARC aggregate report visualizer.

![Dashboard](docs/dashboard-light.png#gh-light-mode-only)
![Dashboard](docs/dashboard-dark.png#gh-dark-mode-only)

Existing DMARC tooling is either paid SaaS, a limited online service, or a
sprawling multi-container stack. This project is the opposite: **one Python
process, one SQLite file, one gorgeous dashboard.**

- Logs into your IMAP mailbox, finds DMARC aggregate reports (XML, `.gz`,
  `.zip`), imports them into SQLite — on startup, on a configurable
  interval, and on demand via the *Sync now* button.
- Handles reports for **multiple domains** — the UI has a domain selector.
- Sleek React dashboard: compliance over time, dispositions, DKIM/SPF
  alignment, per-source breakdown, report browser — with a date-range
  selector, smooth transitions, and light/dark mode.
- Runs as a headless service by default; `--open` pops a browser for local use.
- Plain HTTP only — TLS (and auth) belong on your reverse proxy.
- Tiny supply chain: 3 Python runtime dependencies (`fastapi`, `uvicorn`,
  `defusedxml`); IMAP, MIME, zip/gzip handling, and SQLite are standard
  library. The frontend build is static files; nothing from npm runs on
  your server.

## Quick start

Requires Python ≥ 3.11 and (for building the frontend once) Node ≥ 20.

```sh
git clone https://github.com/mauriceKA/dmarc-all-you-need
cd dmarc-all-you-need

# frontend (build once — emits into the Python package)
cd frontend && npm ci && npm run build && cd ..

# backend (the install includes the frontend build)
python -m venv .venv && . .venv/bin/activate
pip install .

# configure
cp config.ini.template config.ini
$EDITOR config.ini

# run (headless service)
dmarcayn --config config.ini

# ...or locally, opening the dashboard in your browser
dmarcayn --config config.ini --open
```

Point `[imap]` at the mailbox that receives your DMARC reports (the `rua=`
address in your DMARC DNS record). The first sync runs immediately on
startup.

A **dedicated mailbox** for the `rua=` address is the recommended setup.
Pointing at a large general-purpose inbox works too: the sync inspects
MIME metadata (`BODYSTRUCTURE`) in batched round trips and only downloads
messages that actually carry a report-shaped attachment — but scanning
tens of thousands of mails still takes a while on the first run. Set
`[imap] since = YYYY-MM-DD` to skip old mail entirely.

## Configuration

Every key is documented in [config.ini.template](config.ini.template).
Highlights:

| Key | Meaning |
|---|---|
| `[imap] delete_after_import` | Delete mails once their report is stored (default `false`; already-imported mails are tracked and never re-read). |
| `[imap] since` | Optional ISO date; older mails are never scanned. Useful for large mailboxes. |
| `[sync] poll_interval_minutes` | Mailbox check interval (default 30). |
| `[server] host` / `port` | Bind address, default `127.0.0.1:8080`. |
| `[storage] database_path` | SQLite file; relative paths resolve against the config file. |
| `[limits] max_attachment_bytes` / `max_decompressed_bytes` | Safety caps for untrusted report attachments. |

### IMAP password

The password does not have to live in the config file. It is resolved from
exactly one of, in this order:

1. `DMARCAYN_IMAP_PASSWORD` environment variable (systemd `EnvironmentFile=`,
   container env),
2. `password_cmd` — a command whose stdout is the password
   (`pass show mail/dmarc`, `secret-tool lookup ...`, `bw get password ...`),
3. `password_file` — a file containing only the password
   (systemd `LoadCredential=`, Docker secrets),
4. `password` — plaintext in `config.ini`, as a quick-start fallback.
   If you use it, `chmod 600 config.ini`.

## Deployment on a VPS

The app serves plain HTTP without authentication — bind it to `127.0.0.1`
(the default) and put a reverse proxy with TLS in front.

Caddy (automatic TLS):

```caddy
dmarc.example.com {
    reverse_proxy 127.0.0.1:8080
    # optionally require login:
    # basic_auth {
    #     admin $2a$14$...   # generate with: caddy hash-password
    # }
}
```

nginx:

```nginx
server {
    listen 443 ssl;
    server_name dmarc.example.com;
    # ssl_certificate ...; ssl_certificate_key ...;
    # optionally: auth_basic "dmarc"; auth_basic_user_file /etc/nginx/htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8080;
    }
}
```

systemd unit with the password kept out of the config file
(`/etc/systemd/system/dmarcayn.service`):

```ini
[Unit]
Description=DMARC report visualizer
After=network-online.target
Wants=network-online.target

[Service]
User=dmarcayn
WorkingDirectory=/opt/dmarc-all-you-need
ExecStart=/opt/dmarc-all-you-need/.venv/bin/dmarcayn --config /etc/dmarcayn/config.ini
LoadCredential=imap_password:/etc/dmarcayn/imap_password
Restart=on-failure

# hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/dmarcayn
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

with `password_file = /run/credentials/dmarcayn.service/imap_password` in
the `[imap]` section and `database_path = /var/lib/dmarcayn/dmarc.sqlite`
under `[storage]`.

## Development

```sh
pip install -e '.[dev]'
pytest                        # backend tests
ruff check backend tests     # lint

cd frontend
npm run dev                   # Vite dev server on :5173, proxies /api to 127.0.0.1:8080
```

Run the backend (`dmarcayn --config config.ini`) in a second terminal and
develop the UI against the live API with hot reload.

## Security

- **Reports are untrusted third-party input.** XML is parsed exclusively
  with `defusedxml` (XXE and entity-expansion safe); attachments are
  size-capped and stream-decompressed with hard output limits (gzip/zip
  bombs); zip archives must contain exactly one member and are never
  extracted to disk.
- **IMAP is TLS-only** with certificate verification
  (`ssl.create_default_context()`); there is no plaintext option.
- **No authentication by design** — the server binds `127.0.0.1` by
  default. Expose it only through a reverse proxy that terminates TLS and,
  if needed, adds auth.
- **Secrets stay out of the repo and the logs**: `config.ini`, databases,
  and `.env` files are gitignored; error messages never include password
  material.
- **Dependency budget** (enforced in review): 3 Python runtime packages,
  frontend lockfile committed. PRs adding dependencies need a strong case.

## License

Copyright © 2026 Patrik Spieß

Licensed under [AGPL-3.0-or-later](LICENSE) — if you run a modified version
as a network service, you must offer its source to your users.

If the AGPL's obligations don't fit your use case (e.g. offering this as
part of a closed-source product or hosted service), a **commercial parallel
license** is available — contact <post@patrik-spiess.de>.

Note for contributors: to keep dual licensing possible, contributions
require a sign-off consenting to the license grant described in
[CONTRIBUTING.md](CONTRIBUTING.md) — in exchange, accepted contributions
are guaranteed to always remain available under the AGPL.
