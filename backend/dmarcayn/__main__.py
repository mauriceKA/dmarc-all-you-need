"""CLI entry point: dmarcayn [--config config.ini] [--port N] [--open]."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import webbrowser

import uvicorn

from .config import ConfigError, load_config
from .db import Database
from .poller import Poller
from .server import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dmarcayn",
        description="Minimal, beautiful, self-hostable DMARC aggregate report visualizer.",
    )
    parser.add_argument(
        "--config", default="config.ini", help="path to config file (default: ./config.ini)"
    )
    parser.add_argument("--port", type=int, help="override [server] port from the config")
    parser.add_argument(
        "--open", action="store_true", help="open the dashboard in your browser after startup"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    )

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    host = config.server.host
    port = args.port if args.port is not None else config.server.port

    db = Database(config.storage.database_path)
    poller = Poller(config, db)
    app = create_app(config, db, poller)
    poller.start()  # first loop iteration = sync on startup

    if args.open:
        url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}/"  # noqa: S104
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    finally:
        poller.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
