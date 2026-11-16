"""Export every translatable string of Sorry We're Closed into JSON templates.

Usage (from the game folder):

    python tools\\extract.py
    python tools\\extract.py --bundle-dir "D:\\...\\StandaloneWindows64"
    python tools\\extract.py --out translations\\uk

The script is read-only: it never modifies the game files.  It writes

    translations/uk/ui_text.json    TextTable strings (settings menu, prompts, ...)
    translations/uk/dialogue.json   all dialogue lines
    translations/uk/assets.json     actor / item / location names + descriptions
    translations/uk/meta.json       statistics about the exported game build

Only the "uk" values have to be filled in.  Empty values fall back to English
inside the game, so a partially translated file is always safe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import lib_swc as swc


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _clean(value) -> str:
    return "" if value is None else str(value)


def _field_value(fields, title: str) -> str:
    field = swc.field_lookup(fields, title)
    return _clean(field.value) if field is not None else ""


def _actor_names(database) -> dict[int, str]:
    names: dict[int, str] = {}
    for actor in database.actors:
        display = _field_value(actor.fields, "Display Name")
        name = _field_value(actor.fields, "Name")
        names[int(actor.id)] = display or name
    return names


def _entry_speaker(entry, actor_names: dict[int, str]) -> str:
    field = swc.field_lookup(entry.fields, "Actor")
    if field is None:
        return ""
    try:
        actor_id = int(str(field.value))
    except (TypeError, ValueError):
        return ""
    return actor_names.get(actor_id, "")


def _table_snapshot(table) -> tuple:
    """Stable representation used to compare duplicated TextTable copies."""
    languages = tuple(zip(table.m_languageKeys, table.m_languageValues))
    fields = tuple(
        (f.m_fieldName, tuple(f.m_keys), tuple(f.m_values))
        for f in table.m_fieldValues
    )
    return (languages, int(table.m_nextLanguageID), fields)


def _database_snapshot(database) -> tuple:
    entries = 0
    digest = hashlib.sha256()
    for conversation in database.conversations:
        digest.update(str(int(conversation.id)).encode())
        for entry in conversation.dialogueEntries:
            entries += 1
            digest.update(b"\x00")
            digest.update(str(int(entry.id)).encode())
            digest.update(b"\x01")
            digest.update(_field_value(entry.fields, "Dialogue Text").encode("utf-8"))
            digest.update(b"\x02")
    return (len(database.conversations), entries, digest.hexdigest())


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------

def export_ui(tables: dict, canonical: dict[str, tuple]) -> dict:
    ui: dict[str, dict[str, dict[str, str]]] = {}
    for table_name in sorted(canonical):
        table = tables[table_name]
        fields: dict[str, dict[str, str]] = {}
        for field in table.m_fieldValues:
            values = dict(zip(field.m_keys, field.m_values))
            fields[field.m_fieldName] = {
                "en": _clean(values.get(0, "")),
                "uk": "",
            }
        ui[table_name] = fields
    return ui


def export_dialogue(database, actor_names: dict[int, str]) -> tuple[dict, dict]:
    conversations = []
    exported = 0
    skipped = 0
    for conversation in sorted(database.conversations, key=lambda c: int(c.id)):
        title = _field_value(conversation.fields, "Title")
        entries = []
        for entry in sorted(conversation.dialogueEntries, key=lambda e: int(e.id)):
            english = _field_value(entry.fields, "Dialogue Text")
            if not english.strip():
                skipped += 1
                continue
            entries.append({
                "id": int(entry.id),
                "speaker": _entry_speaker(entry, actor_names),
                "en": english,
                "uk": "",
            })
            exported += 1
        if entries:
            conversations.append({
                "id": int(conversation.id),
                "title": title,
                "entries": entries,
            })
    payload = {"conversations": conversations}
    stats = {
        "conversations": len(conversations),
        "entries": exported,
        "entries_without_text": skipped,
    }
    return payload, stats


def export_assets(database) -> dict:
    result: dict[str, list] = {}
    for kind, collection in (
        ("actors", database.actors),
        ("items", database.items),
        ("locations", database.locations),
    ):
        bases: set[str] = set()
        for asset in collection:
            for field in asset.fields:
                title = getattr(field, "title", "")
                if title.endswith(" fr"):
                    bases.add(title[:-3])
        rows = []
        for asset in sorted(collection, key=lambda a: int(a.id)):
            fields: dict[str, dict[str, str]] = {}
            for base in sorted(bases):
                if swc.field_lookup(asset.fields, base + " fr") is None:
                    continue
                fields[base] = {
                    "en": _field_value(asset.fields, base),
                    "uk": "",
                }
            if not fields:
                continue
            rows.append({
                "id": int(asset.id),
                "name": _field_value(asset.fields, "Name")
                        or _field_value(asset.fields, "Display Name"),
                "fields": fields,
            })
        result[kind] = rows
    return result


# --------------------------------------------------------------------------
# merging with a previous export (keeps already translated text)
# --------------------------------------------------------------------------

def _read_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        swc.warn(f"could not read {path.name} ({exc}); starting fresh")
        return None


def merge_previous(out: Path, ui: dict, dialogue: dict, assets: dict) -> int:
    """Carry existing `uk` values over into the freshly exported templates."""
    kept = 0

    previous_ui = _read_json(out / "ui_text.json") or {}
    for table_name, fields in ui.items():
        old_fields = previous_ui.get(table_name) or {}
        for field_name, data in fields.items():
            old = old_fields.get(field_name)
            if isinstance(old, dict):
                value = old.get("uk")
                if isinstance(value, str) and value.strip():
                    data["uk"] = value
                    kept += 1

    previous_dialogue = _read_json(out / "dialogue.json") or {}
    old_entries: dict[tuple[int, int], str] = {}
    for conversation in previous_dialogue.get("conversations", []) or []:
        try:
            conversation_id = int(conversation["id"])
        except (KeyError, TypeError, ValueError):
            continue
        for entry in conversation.get("entries", []) or []:
            try:
                old_entries[(conversation_id, int(entry["id"]))] = entry.get("uk")
            except (KeyError, TypeError, ValueError):
                continue
    for conversation in dialogue["conversations"]:
        for entry in conversation["entries"]:
            value = old_entries.get((conversation["id"], entry["id"]))
            if isinstance(value, str) and value.strip():
                entry["uk"] = value
                kept += 1

    previous_assets = _read_json(out / "assets.json") or {}
    old_assets: dict[tuple[str, int, str], str] = {}
    for kind, rows in previous_assets.items():
        for row in rows or []:
            try:
                asset_id = int(row["id"])
            except (KeyError, TypeError, ValueError):
                continue
            for base, data in (row.get("fields") or {}).items():
                old_assets[(kind, asset_id, base)] = (data or {}).get("uk")
    for kind, rows in assets.items():
        for row in rows:
            for base, data in row["fields"].items():
                value = old_assets.get((kind, row["id"], base))
                if isinstance(value, str) and value.strip():
                    data["uk"] = value
                    kept += 1

    return kept


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=swc.BUNDLE_DIR)
    parser.add_argument("--out", type=Path,
                        default=swc.TRANSLATIONS_DIR / swc.LANGUAGE_CODE)
    args = parser.parse_args(argv)

    if not args.bundle_dir.is_dir():
        print(f"Bundle folder not found: {args.bundle_dir}", file=sys.stderr)
        return 2

    paths = swc.bundle_paths(args.bundle_dir)
    swc.say(f"Game root : {swc.GAME_ROOT}")
    swc.say(f"Bundles   : {len(paths)} in {args.bundle_dir}")
    swc.say("")

    # -- first occurrence of every asset type; duplicated copies are compared --
    canonical_tables: dict[str, tuple] = {}
    table_snapshots: dict[str, set[str]] = {}
    table_owner: dict[str, str] = {}
    canonical_database = None
    canonical_database_bundle = None
    database_snapshots: set[str] = set()
    dropdown_options: set[tuple[str, ...]] = set()
    dropdown_bundles: set[str] = set()
    table_bundles: set[str] = set()
    database_bundles: set[str] = set()

    for index, path in enumerate(paths):
        if index % 10 == 0:
            swc.say(f"  scanning {index + 1}/{len(paths)} ...")
        env = swc.load_bundle(path)
        for behaviour in swc.iter_monobehaviours(env):
            class_name = swc.script_class(behaviour)
            if class_name == "TextTable":
                name = str(getattr(behaviour, "m_Name", ""))
                if not name:
                    continue
                digest = hashlib.sha256(
                    repr(_table_snapshot(behaviour)).encode("utf-8")
                ).hexdigest()
                table_snapshots.setdefault(name, set()).add(digest)
                table_bundles.add(path.name)
                if name not in canonical_tables:
                    canonical_tables[name] = (path.name, behaviour)
                    table_owner[name] = path.name
            elif class_name == "DialogueDatabase":
                database_bundles.add(path.name)
                snapshot = _database_snapshot(behaviour)
                database_snapshots.add(repr(snapshot))
                if canonical_database is None:
                    canonical_database = behaviour
                    canonical_database_bundle = path.name
            elif class_name == "TMP_Dropdown":
                options = getattr(getattr(behaviour, "m_Options", None),
                                  "m_Options", None)
                if not options:
                    continue
                texts = tuple(str(getattr(o, "m_Text", "")) for o in options)
                if any(text.startswith("language_option_") for text in texts):
                    dropdown_options.add(texts)
                    dropdown_bundles.add(path.name)
        del env

    swc.say("")
    if canonical_database is None:
        print("No DialogueDatabase found - wrong folder?", file=sys.stderr)
        return 2

    # -- consistency report -------------------------------------------------
    swc.say("Duplicated asset check:")
    mismatched = 0
    for name, digests in sorted(table_snapshots.items()):
        if len(digests) > 1:
            mismatched += 1
            swc.warn(f"TextTable '{name}' differs across bundles "
                     f"({len(digests)} variants)")
    swc.say(f"  TextTable copies : {len(canonical_tables)} tables in "
            f"{len(table_bundles)} bundles")
    swc.say(f"  DialogueDatabase : {len(database_snapshots)} variant(s) in "
            f"{len(database_bundles)} bundles")
    swc.say(f"  Language dropdown: {len(dropdown_options)} variant(s) in "
            f"{len(dropdown_bundles)} bundles")
    if mismatched:
        swc.warn("Some copies differ; the apply step writes values by field "
                 "name / id, so every copy still receives the translation.")

    # -- build the templates ------------------------------------------------
    tables = {name: data[1] for name, data in canonical_tables.items()}
    ui = export_ui(tables, canonical_tables)

    settings_table = None
    for name in ui:
        if name.lower() == "settings menu":
            settings_table = name
            break
    if settings_table is not None:
        ui[settings_table]["language_option_uk"] = {
            "en": swc.LANGUAGE_LABEL,
            "uk": swc.LANGUAGE_LABEL,
        }

    actor_names = _actor_names(canonical_database)
    dialogue, dialogue_stats = export_dialogue(canonical_database, actor_names)
    assets = export_assets(canonical_database)

    args.out.mkdir(parents=True, exist_ok=True)
    kept = merge_previous(args.out, ui, dialogue, assets)
    if kept:
        swc.say(f"  kept {kept} existing Ukrainian translation(s)")

    def write(name: str, payload) -> None:
        target = args.out / name
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        swc.say(f"  wrote {target}")

    swc.say("")
    write("ui_text.json", ui)
    write("dialogue.json", dialogue)
    write("assets.json", assets)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "language": swc.LANGUAGE_CODE,
        "game_root": str(swc.GAME_ROOT),
        "bundle_dir": str(args.bundle_dir),
        "bundle_count": len(paths),
        "text_tables": {
            "tables": len(canonical_tables),
            "bundles": len(table_bundles),
            "fields": sum(len(fields) for fields in ui.values()),
            "variants": {
                name: len(digests)
                for name, digests in table_snapshots.items()
                if len(digests) > 1
            },
        },
        "dialogue": {
            **dialogue_stats,
            "bundles": len(database_bundles),
            "variants": len(database_snapshots),
            "source_bundle": canonical_database_bundle,
        },
        "assets": {
            kind: len(rows) for kind, rows in assets.items()
        },
        "dropdown_bundles": len(dropdown_bundles),
        "dropdown_variants": [list(options) for options in dropdown_options],
    }
    write("meta.json", meta)

    swc.say("")
    swc.say("Done. Translate the \"uk\" values in the JSON files, then run:")
    swc.say("  python tools\\apply.py --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
