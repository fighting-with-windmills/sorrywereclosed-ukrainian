"""Shared helpers for the Sorry We're Closed Ukrainian localization tools.

The game is a Unity (Mono) build that keeps almost every asset inside
Addressables bundles:

    Sorry We're Closed_Data/StreamingAssets/aa/StandaloneWindows64/*.bundle

Localization is implemented with Pixel Crushers Dialogue System:

  * `PixelCrushers.TextTable`  (MonoBehaviour)  -> UI strings
  * `DialogueDatabase`         (MonoBehaviour)  -> dialogue / actor / item / location text
  * `TMP_Dropdown`             (MonoBehaviour)  -> the language selector

This module only contains discovery / cloning / saving helpers.  It never
touches the game files by itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

import UnityPy
from UnityPy.classes.UnknownObject import UnknownObject

# Windows consoles / redirected output: never crash on Cyrillic output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

BACKUP_DIRNAME = "_uk_backup"
LANGUAGE_CODE = "uk"
LANGUAGE_LABEL = "\u0423\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u0430"  # Українська


def find_game_root(start: Path) -> Path:
    """Locate the game folder (the one that contains the .exe)."""
    env = os.environ.get("SWC_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "Sorry We're Closed.exe").is_file():
            return candidate
    # tools/ lives directly inside the game folder
    return start.parent


TOOLS_DIR = Path(__file__).resolve().parent
GAME_ROOT = find_game_root(TOOLS_DIR)

DATA_DIRNAME = "Sorry We're Closed_Data"
DATA_DIR = GAME_ROOT / DATA_DIRNAME
BUNDLE_DIR = DATA_DIR / "StreamingAssets" / "aa" / "StandaloneWindows64"
MANAGED_DIR = DATA_DIR / "Managed"
DEFAULT_BACKUP_DIR = GAME_ROOT / BACKUP_DIRNAME

TRANSLATIONS_DIR = GAME_ROOT / "translations"


# --------------------------------------------------------------------------
# Tiny console helpers
# --------------------------------------------------------------------------

def say(message: str = "") -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"  ! {message}", flush=True)


# --------------------------------------------------------------------------
# Bundle access
# --------------------------------------------------------------------------

def bundle_paths(bundle_dir: Path) -> list[Path]:
    return sorted(Path(bundle_dir).glob("*.bundle"))


def load_bundle(path: Path):
    return UnityPy.load(str(path))


def bundle_bytes(env) -> bytes:
    """Serialise a loaded bundle back to the original on-disk format."""
    files = list(env.files.values())
    if len(files) != 1:
        raise RuntimeError(
            f"expected exactly one internal file per .bundle, got {len(files)}"
        )
    return files[0].save(packer="original")


def save_bundle(env, dest: Path) -> None:
    """Write a loaded bundle to `dest` atomically."""
    data = bundle_bytes(env)
    tmp = dest.with_name(dest.name + ".uk_tmp")
    tmp.write_bytes(data)
    try:
        os.replace(tmp, dest)
    except OSError:
        # Windows can keep a handle open; give the GC a chance to close it.
        import gc
        gc.collect()
        os.replace(tmp, dest)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# UnityEngine object helpers
# --------------------------------------------------------------------------

def script_class(mono_behaviour) -> str | None:
    """Return the C# class name of a MonoBehaviour asset (or None)."""
    try:
        script = getattr(mono_behaviour, "m_Script", None)
        if script is None:
            return None
        return getattr(script.read(), "m_ClassName", None)
    except Exception:
        return None


def gameobject_name(component) -> str:
    try:
        return component.m_GameObject.read().m_Name or ""
    except Exception:
        return ""


def clone_typetree(obj):
    """Copy a UnityPy typetree object (deepcopy fails on TypeTreeNode)."""
    values = {k: v for k, v in obj.__dict__.items() if k != "__node__"}
    values = {
        k: (list(v) if isinstance(v, list) else v)
        for k, v in values.items()
    }
    return UnknownObject(obj.__node__, **values)


def field_lookup(fields, title: str):
    for field in fields:
        if getattr(field, "title", None) == title:
            return field
    return None


def make_localization_field(template_field, title: str, value: str = ""):
    """Create a Pixel Crushers `Field` of type Localization."""
    new_field = clone_typetree(template_field)
    new_field.title = title
    new_field.value = value
    try:
        new_field.type = 4
        new_field.typeString = "CustomFieldType_Localization"
    except Exception:
        pass
    return new_field


# --------------------------------------------------------------------------
# TextTable helpers
# --------------------------------------------------------------------------

def table_language_id(table, language: str = LANGUAGE_CODE) -> int | None:
    keys = list(table.m_languageKeys)
    if language not in keys:
        return None
    return int(table.m_languageValues[keys.index(language)])


def ensure_table_language(table, language: str = LANGUAGE_CODE) -> int:
    """Make sure a TextTable has a language entry and return its numeric id."""
    keys = list(table.m_languageKeys)
    if language in keys:
        return int(table.m_languageValues[keys.index(language)])

    new_id = int(table.m_nextLanguageID)
    table.m_languageKeys = keys + [language]
    table.m_languageValues = list(table.m_languageValues) + [new_id]
    table.m_nextLanguageID = new_id + 1
    return new_id


def set_field_language(field, language_id: int, value: str) -> bool:
    """Set one language value of a TextTableField; return True if it changed."""
    keys = list(field.m_keys)
    values = list(field.m_values)
    if language_id in keys:
        index = keys.index(language_id)
        if values[index] == value:
            return False
        values[index] = value
    else:
        keys.append(language_id)
        values.append(value)
    field.m_keys = keys
    field.m_values = values
    return True


def text_table_fields(table) -> dict[str, Any]:
    return {f.m_fieldName: f for f in table.m_fieldValues}


# --------------------------------------------------------------------------
# Manifest used by the apply/restore scripts
# --------------------------------------------------------------------------

class Manifest:
    """Tracks which bundles we modified and what the pristine bytes were."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict[str, str]] = {}
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.data = raw.get("bundles", {})
            except Exception:
                self.data = {}

    def get(self, bundle_name: str) -> dict[str, str] | None:
        return self.data.get(bundle_name)

    def put(self, bundle_name: str, original_sha: str,
            patched_sha: str) -> None:
        self.data[bundle_name] = {
            "original_sha256": original_sha,
            "patched_sha256": patched_sha,
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "game_root": str(GAME_ROOT),
            "bundles": self.data,
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def copy_with_dirs(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def iter_monobehaviours(env) -> Iterable[Any]:
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            yield obj.read()
        except Exception:
            continue
