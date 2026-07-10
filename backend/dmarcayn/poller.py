"""Background sync poller: one daemon thread owns all IMAP + DB writes.

POST /api/sync only sets the wake event, so concurrent syncs are
structurally impossible — no locking around IMAP or the database.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict
from typing import Any

from .config import Config
from .db import Database
from .imap_client import ImapClient, ImapError
from .sync import SyncResult, run_sync

logger = logging.getLogger(__name__)


class SyncStatus:
    """Thread-safe snapshot of the poller's state, read by the API."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self._last_run_at: int | None = None
        self._last_result: SyncResult | None = None
        self._last_error: str | None = None
        self._next_run_at: int | None = None

    def start_run(self) -> None:
        with self._lock:
            self._running = True

    def finish_run(
        self, result: SyncResult | None, error: str | None, next_run_at: int
    ) -> None:
        with self._lock:
            self._running = False
            self._last_run_at = int(time.time())
            if result is not None:
                self._last_result = result
            self._last_error = error
            self._next_run_at = next_run_at

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            last_result = None
            if self._last_result is not None:
                last_result = asdict(self._last_result)
                del last_result["error_details"]  # internal; keep the payload lean
            return {
                "running": self._running,
                "last_run_at": self._last_run_at,
                "last_result": last_result,
                "last_error": self._last_error,
                "next_run_at": self._next_run_at,
            }


class Poller:
    def __init__(self, config: Config, db: Database):
        self._config = config
        self._db = db
        self.status = SyncStatus()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="sync-poller", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=timeout)
        self._db.close()  # the poller thread's connection

    def trigger(self) -> bool:
        """Request a sync now. Returns False if one is already running."""
        if self.status.running:
            return False
        self._wake.set()
        return True

    # -- internals ----------------------------------------------------------

    def _loop(self) -> None:
        interval = self._config.sync.poll_interval_minutes * 60
        while not self._stop.is_set():
            self.status.start_run()
            result: SyncResult | None = None
            error: str | None = None
            try:
                with ImapClient(self._config.imap) as client:
                    result = run_sync(client, self._db, self._config)
                logger.info(
                    "sync done: %d fetched, %d imported, %d duplicates, %d errors",
                    result.fetched, result.imported, result.duplicates, result.errors,
                )
            except ImapError as exc:
                error = str(exc)
                logger.error("sync failed: %s", exc)
            except Exception:  # keep the poller alive no matter what
                error = "internal error during sync (see server log)"
                logger.exception("unexpected error during sync")
            finally:
                self.status.finish_run(result, error, int(time.time()) + interval)
                self._db.set_meta("last_sync_at", str(int(time.time())))

            self._wake.wait(timeout=interval)
            self._wake.clear()
