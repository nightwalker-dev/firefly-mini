"""Tests for cross-platform abstraction layer (firefly.core.platform)."""

from __future__ import annotations

from pathlib import Path

from firefly.core.platform import (
    decode_output,
    hidden_window_kwargs,
    new_process_group_kwargs,
    os_name,
    os_pretty_name,
    resolve_shell,
    root_path,
    secure_chmod,
    user_config_dir,
    user_data_dir,
)


def test_os_detection():
    name = os_name()
    assert name in ("linux", "windows", "macos", "unix")
    pretty = os_pretty_name()
    assert len(pretty) > 0


def test_user_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FIREFLY_DATA_DIR", str(tmp_path / "custom_data"))
    monkeypatch.setenv("FIREFLY_CONFIG_DIR", str(tmp_path / "custom_config"))

    assert user_data_dir() == tmp_path / "custom_data"
    assert user_config_dir() == tmp_path / "custom_config"


def test_default_user_dirs(monkeypatch):
    monkeypatch.delenv("FIREFLY_DATA_DIR", raising=False)
    monkeypatch.delenv("FIREFLY_CONFIG_DIR", raising=False)

    data = user_data_dir()
    config = user_config_dir()
    assert "firefly-mini" in str(data)
    assert "firefly-mini" in str(config)


def test_resolve_shell_auto():
    spec = resolve_shell("auto")
    assert spec is not None
    assert spec.name in ("bash", "sh", "zsh", "pwsh", "powershell", "cmd")
    argv = spec.build_argv("echo test")
    assert len(argv) >= 2


def test_resolve_shell_explicit():
    spec = resolve_shell("sh")
    if spec:
        assert spec.kind == "posix"
        argv = spec.build_argv("ls")
        assert argv[-1] == "ls"


def test_process_helpers():
    pg_kwargs = new_process_group_kwargs()
    assert isinstance(pg_kwargs, dict)
    win_kwargs = hidden_window_kwargs()
    assert isinstance(win_kwargs, dict)


def test_decode_output():
    assert decode_output(None) == ""
    assert decode_output("hello") == "hello"
    assert decode_output(b"binary \xf0\x9f\x90\xbe") == "binary 🐾"


def test_root_path():
    rp = root_path()
    assert rp.exists()


def test_secure_chmod(tmp_path: Path):
    test_f = tmp_path / "test_perm.txt"
    test_f.write_text("secure")
    res = secure_chmod(test_f, 0o600)
    assert isinstance(res, bool)
