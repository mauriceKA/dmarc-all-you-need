import pytest

from dmarcayn.config import PASSWORD_ENV_VAR, ConfigError, load_config

MINIMAL = """
[imap]
host = imap.example.com
username = reports@example.com
{password_lines}

[server]

[storage]
database_path = data/dmarc.sqlite
"""


def write_config(tmp_path, password_lines):
    path = tmp_path / "config.ini"
    path.write_text(MINIMAL.format(password_lines=password_lines))
    return path


def test_defaults_and_paths(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    cfg = load_config(write_config(tmp_path, "password = hunter2"))
    assert cfg.imap.host == "imap.example.com"
    assert cfg.imap.port == 993
    assert cfg.imap.password == "hunter2"
    assert cfg.imap.mailbox == "INBOX"
    assert cfg.imap.delete_after_import is False
    assert cfg.sync.poll_interval_minutes == 30
    assert cfg.server.host == "127.0.0.1"
    assert cfg.server.port == 8080
    assert cfg.server.static_dir is None
    # relative database_path resolves against the config file's directory
    assert cfg.storage.database_path == (tmp_path / "data" / "dmarc.sqlite").resolve()
    assert cfg.limits.max_attachment_bytes == 25 * 1024 * 1024


def test_password_not_in_repr(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    cfg = load_config(write_config(tmp_path, "password = hunter2"))
    assert "hunter2" not in repr(cfg)


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.ini")


def test_template_placeholder_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    with pytest.raises(ConfigError, match="CHANGE_ME"):
        load_config(write_config(tmp_path, "password = CHANGE_ME"))


def test_no_password_source(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    with pytest.raises(ConfigError, match="no password configured"):
        load_config(write_config(tmp_path, ""))


def test_multiple_password_sources_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    with pytest.raises(ConfigError, match="at most one"):
        load_config(write_config(tmp_path, "password = a\npassword_file = b"))


def test_env_var_wins(tmp_path, monkeypatch):
    monkeypatch.setenv(PASSWORD_ENV_VAR, "from-env")
    cfg = load_config(write_config(tmp_path, "password = from-file"))
    assert cfg.imap.password == "from-env"


def test_password_file(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    (tmp_path / "secret").write_text("s3cret\n")
    cfg = load_config(write_config(tmp_path, "password_file = secret"))
    assert cfg.imap.password == "s3cret"


def test_password_file_missing(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    with pytest.raises(ConfigError, match="cannot read password_file"):
        load_config(write_config(tmp_path, "password_file = missing"))


def test_password_cmd(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    cfg = load_config(write_config(tmp_path, "password_cmd = echo cmd-secret"))
    assert cfg.imap.password == "cmd-secret"


def test_password_cmd_failure_hides_output(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    with pytest.raises(ConfigError, match="status 7") as excinfo:
        load_config(
            write_config(tmp_path, 'password_cmd = sh -c "echo topsecret; exit 7"')
        )
    assert "topsecret" not in str(excinfo.value)


def test_invalid_int(tmp_path, monkeypatch):
    monkeypatch.delenv(PASSWORD_ENV_VAR, raising=False)
    path = write_config(tmp_path, "password = x\nport = many")
    with pytest.raises(ConfigError, match="must be an integer"):
        load_config(path)
