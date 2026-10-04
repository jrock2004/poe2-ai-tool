import asyncio
import sys
from pathlib import Path

import pytest

from poe2_mcp import poe2scout, server
from poe2_mcp._cache import Fetched
from poe2_mcp.store import data_dir, read_config, write_config


def _home(monkeypatch, tmp_path: Path) -> Path:
    """Point the home directory at tmp_path on every platform; Path.home() reads HOME or USERPROFILE."""
    monkeypatch.delenv("POE2_DATA_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_data_dir_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("POE2_DATA_DIR", str(tmp_path / "custom"))
    monkeypatch.setattr(sys, "platform", "win32")
    assert data_dir() == tmp_path / "custom"


def test_data_dir_windows_uses_appdata(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert data_dir() == tmp_path / "Roaming" / "poe2-ai-tools"


def test_data_dir_macos_uses_application_support(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    assert data_dir() == home / "Library" / "Application Support" / "poe2-ai-tools"


def test_data_dir_linux_uses_xdg_data_home(monkeypatch, tmp_path):
    _home(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert data_dir() == tmp_path / "xdg" / "poe2-ai-tools"


def test_data_dir_linux_falls_back_to_local_share(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert data_dir() == home / ".local" / "share" / "poe2-ai-tools"


def test_read_config_missing_file_is_empty(tmp_path):
    assert read_config(tmp_path / "nowhere") == {}


def test_write_then_read_round_trips_and_creates_the_dir(tmp_path):
    root = tmp_path / "a" / "b"
    write_config(root, {"league": "Forbidden Rites"})
    assert read_config(root) == {"league": "Forbidden Rites"}


def test_write_config_uses_lf_newlines(tmp_path):
    write_config(tmp_path, {"league": "Forbidden Rites", "x": [1, 2]})
    assert b"\r" not in (tmp_path / "config.json").read_bytes()


def test_write_config_leaves_no_temp_file(tmp_path):
    write_config(tmp_path, {"league": "Forbidden Rites"})
    write_config(tmp_path, {"league": "Standard"})
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"]


def test_read_config_corrupt_json_raises_naming_the_path(tmp_path):
    (tmp_path / "config.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="config.json"):
        read_config(tmp_path)


# --- set_league (server tool): validates against poe2scout before it writes anything ----------------

LEAGUES = [
    {"Value": "Standard", "ShortName": "Std", "IsCurrent": False},
    {"Value": "Forbidden Rites", "ShortName": "FR", "IsCurrent": True},
]


class _FakeScout(poe2scout.Poe2ScoutClient):
    async def get_leagues(self):
        return Fetched(body=LEAGUES, fetched_at=0.0)


def _set_league(monkeypatch, tmp_path, league: str):
    monkeypatch.setenv("POE2_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(server, "_scout", _FakeScout())
    return asyncio.run(server.set_league(league))


def test_set_league_saves_the_canonical_value_for_a_short_name(monkeypatch, tmp_path):
    result = _set_league(monkeypatch, tmp_path, "fr")
    assert result["league"] == "Forbidden Rites"
    assert read_config(tmp_path) == {"league": "Forbidden Rites"}


def test_set_league_rejects_an_unknown_league_and_writes_nothing(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError, match="Dawn of the Hunt"):
        _set_league(monkeypatch, tmp_path, "Dawn of the Hunt")
    assert not (tmp_path / "config.json").exists()


def test_set_league_keeps_other_config_keys(monkeypatch, tmp_path):
    write_config(tmp_path, {"other": 1})
    _set_league(monkeypatch, tmp_path, "Standard")
    assert read_config(tmp_path) == {"other": 1, "league": "Standard"}
