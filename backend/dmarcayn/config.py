"""Load and validate config.ini into a typed, immutable Config."""

from __future__ import annotations

import configparser
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

PASSWORD_ENV_VAR = "DMARCAYN_IMAP_PASSWORD"  # noqa: S105 -- env var name, not a secret


class ConfigError(Exception):
    """Raised for a missing, unreadable, or invalid configuration."""


@dataclass(frozen=True)
class ImapConfig:
    host: str
    port: int
    username: str
    password: str = field(repr=False)
    mailbox: str
    delete_after_import: bool
    since: date | None = None  # ignore mails older than this (SEARCH SINCE)


@dataclass(frozen=True)
class SyncConfig:
    poll_interval_minutes: int


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    static_dir: Path | None


@dataclass(frozen=True)
class StorageConfig:
    database_path: Path


@dataclass(frozen=True)
class LimitsConfig:
    max_attachment_bytes: int
    max_decompressed_bytes: int


@dataclass(frozen=True)
class Config:
    imap: ImapConfig
    sync: SyncConfig
    server: ServerConfig
    storage: StorageConfig
    limits: LimitsConfig


def _resolve_password(section: configparser.SectionProxy, config_dir: Path) -> str:
    """Resolve the IMAP password from env var, password_cmd, password_file, or password.

    Precedence: environment variable > password_cmd > password_file > password.
    Exactly one config-file mechanism may be set; the env var overrides them all.
    """
    env_password = os.environ.get(PASSWORD_ENV_VAR)

    cmd = section.get("password_cmd")
    file_ = section.get("password_file")
    plain = section.get("password")
    configured = [name for name, value in
                  [("password_cmd", cmd), ("password_file", file_), ("password", plain)]
                  if value]
    if len(configured) > 1:
        raise ConfigError(
            f"[imap] sets {' and '.join(configured)}; configure at most one password source"
        )

    if env_password:
        return env_password
    if cmd:
        try:
            result = subprocess.run(  # noqa: S603 -- operator-supplied command by design
                shlex.split(cmd), capture_output=True, text=True, timeout=30, check=True
            )
        except FileNotFoundError as exc:
            raise ConfigError(f"[imap] password_cmd failed: command not found: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ConfigError("[imap] password_cmd timed out after 30s") from exc
        except subprocess.CalledProcessError as exc:
            # Deliberately omit stdout/stderr: they may contain secret material.
            raise ConfigError(
                f"[imap] password_cmd exited with status {exc.returncode}"
            ) from exc
        password = result.stdout.strip()
        if not password:
            raise ConfigError("[imap] password_cmd produced no output")
        return password
    if file_:
        path = (config_dir / file_).resolve() if not Path(file_).is_absolute() else Path(file_)
        try:
            password = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigError(f"[imap] cannot read password_file {path}: {exc}") from exc
        if not password:
            raise ConfigError(f"[imap] password_file {path} is empty")
        return password
    if plain:
        if plain == "CHANGE_ME":
            raise ConfigError("[imap] password is still the template placeholder CHANGE_ME")
        return plain

    raise ConfigError(
        f"[imap] no password configured: set the {PASSWORD_ENV_VAR} environment variable, "
        "or one of password_cmd / password_file / password in config.ini"
    )


def _require(section: configparser.SectionProxy, key: str) -> str:
    value = section.get(key, "").strip()
    if not value:
        raise ConfigError(f"[{section.name}] missing required key: {key}")
    return value


def _get_int(section: configparser.SectionProxy, key: str, default: int | None = None) -> int:
    raw = section.get(key, "").strip()
    if not raw:
        if default is None:
            raise ConfigError(f"[{section.name}] missing required key: {key}")
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"[{section.name}] {key} must be an integer, got {raw!r}") from None
    if value <= 0:
        raise ConfigError(f"[{section.name}] {key} must be positive, got {value}")
    return value


def load_config(path: str | Path) -> Config:
    """Read, validate, and return the configuration at ``path``."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(
            f"config file not found: {path}\n"
            "Copy config.ini.template to config.ini and edit it."
        )
    config_dir = path.resolve().parent

    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(path.read_text(encoding="utf-8"), source=str(path))
    except (configparser.Error, OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot parse {path}: {exc}") from exc

    for name in ("imap", "server", "storage"):
        if name not in parser:
            raise ConfigError(f"missing required section [{name}] in {path}")

    imap_sec = parser["imap"]
    try:
        delete_after_import = imap_sec.getboolean("delete_after_import", fallback=False)
    except ValueError:
        raise ConfigError(
            "[imap] delete_after_import must be a boolean (true/false)"
        ) from None
    since_raw = imap_sec.get("since", "").strip()
    since = None
    if since_raw:
        try:
            since = date.fromisoformat(since_raw)
        except ValueError:
            raise ConfigError(
                f"[imap] since must be an ISO date (YYYY-MM-DD), got {since_raw!r}"
            ) from None
    imap = ImapConfig(
        host=_require(imap_sec, "host"),
        port=_get_int(imap_sec, "port", default=993),
        username=_require(imap_sec, "username"),
        password=_resolve_password(imap_sec, config_dir),
        mailbox=imap_sec.get("mailbox", "INBOX").strip() or "INBOX",
        delete_after_import=delete_after_import,
        since=since,
    )

    sync_sec = parser["sync"] if "sync" in parser else parser["DEFAULT"]
    sync = SyncConfig(poll_interval_minutes=_get_int(sync_sec, "poll_interval_minutes", default=30))

    server_sec = parser["server"]
    static_dir_raw = server_sec.get("static_dir", "").strip()
    server = ServerConfig(
        host=server_sec.get("host", "127.0.0.1").strip() or "127.0.0.1",
        port=_get_int(server_sec, "port", default=8080),
        static_dir=Path(static_dir_raw).resolve() if static_dir_raw else None,
    )

    db_raw = _require(parser["storage"], "database_path")
    db_path = Path(db_raw)
    if not db_path.is_absolute():
        db_path = config_dir / db_path
    storage = StorageConfig(database_path=db_path.resolve())

    limits_sec = parser["limits"] if "limits" in parser else parser["DEFAULT"]
    limits = LimitsConfig(
        max_attachment_bytes=_get_int(limits_sec, "max_attachment_bytes", default=25 * 1024 * 1024),
        max_decompressed_bytes=_get_int(
            limits_sec, "max_decompressed_bytes", default=100 * 1024 * 1024
        ),
    )

    return Config(imap=imap, sync=sync, server=server, storage=storage, limits=limits)
