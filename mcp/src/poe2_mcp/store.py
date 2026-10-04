"""Per-user persistent state owned by the server: one folder outside the install, so it survives
plugin updates and is shared by every Claude client on the machine. File I/O only -- no network.

Today it holds config.json ({"league": ...}, written by the set_league tool). Set POE2_DATA_DIR to
point it elsewhere (tests do).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "poe2-ai-tools"
CONFIG_FILE = "config.json"


def data_dir() -> Path:
    """POE2_DATA_DIR if set; else %APPDATA%\\poe2-ai-tools (Windows),
    ~/Library/Application Support/poe2-ai-tools (macOS), $XDG_DATA_HOME or ~/.local/share/poe2-ai-tools.

    Read at call time, not import time, so a changed environment (or a test) takes effect.
    """
    override = os.environ.get("POE2_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_NAME


def read_config(root: Path) -> dict[str, Any]:
    """root/config.json, or {} if missing. Corrupt JSON raises, naming the path; never silently resets."""
    path = root / CONFIG_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        config = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{path} is not valid JSON ({e}); fix or delete it") from e
    if not isinstance(config, dict):
        raise RuntimeError(f"{path} must hold a JSON object; fix or delete it")
    return config


def write_config(root: Path, config: dict[str, Any]) -> None:
    """Creates root; writes utf-8, newline="\\n", via temp file + os.replace (no half-written config)."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / CONFIG_FILE
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
