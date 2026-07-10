# dmarc-all-you-need

Minimal, beautiful, self-hostable DMARC aggregate report visualizer.

![Dashboard](docs/dashboard-light.png#gh-light-mode-only)
![Dashboard](docs/dashboard-dark.png#gh-dark-mode-only)

Existing DMARC tooling is either paid SaaS, a limited online service, or a
sprawling multi-container stack. This project is the opposite: **one Python
process, one SQLite file, one gorgeous dashboard.**

- Logs into your IMAP mailbox, finds DMARC aggregate reports (XML, `.gz`,
  `.zip`), imports them into SQLite.
- Handles reports for **multiple domains** — the UI has a domain selector.
- Sleek React dashboard with interactive charts and a date-range selector.
- Runs as a headless service by default; `--open` pops a browser for local use.
- Plain HTTP only — TLS (and auth) belong on your reverse proxy.
- Tiny supply chain: 3 Python runtime dependencies (`fastapi`, `uvicorn`,
  `defusedxml`), everything else standard library.

## Quick start

```sh
git clone https://github.com/mauriceKA/dmarc-all-you-need
cd dmarc-all-you-need

# frontend (build once)
cd frontend && npm ci && npm run build && cd ..

# backend
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

## Configuration

See [config.ini.template](config.ini.template) — every key is documented there.

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

## Deployment

*(reverse-proxy and systemd examples to follow)*

## Development

```sh
pip install -e '.[dev]'
pytest                        # backend tests
cd frontend && npm run dev    # Vite dev server, proxies /api to 127.0.0.1:8080
```

## Security

- Reports are untrusted third-party input: XML is parsed with `defusedxml`,
  attachments are size-capped and stream-decompressed to defuse
  decompression bombs.
- The server binds `127.0.0.1` by default and offers no authentication —
  expose it only through a reverse proxy that terminates TLS.
- `config.ini` (credentials) and the SQLite database are gitignored; keep it
  that way.

## License

[AGPL-3.0-or-later](LICENSE)
