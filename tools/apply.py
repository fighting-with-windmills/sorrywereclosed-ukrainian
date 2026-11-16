"""Apply the Ukrainian translations to the game bundles.

Typical workflow:

    python tools\\extract.py          (once, creates translations\\uk\\*.json)
    ...translate the "uk" values...
    python tools\\apply.py            (dry-run: shows what would change)
    python tools\\apply.py --apply    (writes the bundles)
    python tools\\verify.py           (checks the result)

Every modified bundle is backed up first.  Applying again always rebuilds from
the pristine backup, so editing the JSON files and re-running is safe and never
duplicates data.

Useful switches:
    --force            accept bundles whose bytes changed since the backup
    --only <text>      only process bundles whose file name contains <text>
    --fonts            replace the source TTFs with translations\\uk\\fonts
    --no-dialogue / --no-ui / --no-dropdown
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fonts
import lib_swc as swc


# --------------------------------------------------------------------------
# translation loading
# --------------------------------------------------------------------------

class Translations:
    def __init__(self, directory: Path, allow_missing: bool = False):
        self.directory = directory
        self.ui: dict[str, dict[str, dict[str, str]]] = {}
        self.dialogue: dict[tuple[int, int], str] = {}
        self.assets: dict[str, dict[int, dict[str, str]]] = {}

        ui_path = directory / "ui_text.json"
        dialogue_path = directory / "dialogue.json"
        assets_path = directory / "assets.json"

        if not ui_path.is_file() and not dialogue_path.is_file():
            if allow_missing:
                return
            raise SystemExit(
                f"No translation files in {directory}.\n"
                "Run: python tools\\extract.py"
            )

        if ui_path.is_file():
            self.ui = json.loads(ui_path.read_text(encoding="utf-8"))
        if dialogue_path.is_file():
            raw = json.loads(dialogue_path.read_text(encoding="utf-8"))
            for conversation in raw.get("conversations", []):
                conversation_id = int(conversation["id"])
                for entry in conversation.get("entries", []):
                    self.dialogue[(conversation_id, int(entry["id"]))] = \
                        str(entry.get("uk") or "")
        if assets_path.is_file():
            raw = json.loads(assets_path.read_text(encoding="utf-8"))
            for kind, rows in raw.items():
                bucket = self.assets.setdefault(kind, {})
                for row in rows:
                    bucket[int(row["id"])] = {
                        base: str(data.get("uk") or "")
                        for base, data in (row.get("fields") or {}).items()
                    }

    # -- lookups ---------------------------------------------------------
    def ui_value(self, table: str, field: str) -> str | None:
        table_data = self.ui.get(table)
        if table_data is None or field not in table_data:
            return None
        return str(table_data[field].get("uk") or "")

    def ui_default(self, table: str, field: str) -> str | None:
        table_data = self.ui.get(table)
        if table_data is None or field not in table_data:
            return None
        return str(table_data[field].get("en") or "")

    def stats(self) -> dict:
        dialogue_total = len(self.dialogue)
        dialogue_done = sum(1 for v in self.dialogue.values() if v.strip())
        ui_fields = [(t, f, d) for t, fields in self.ui.items()
                     for f, d in fields.items()]
        ui_done = sum(1 for _, _, d in ui_fields if str(d.get("uk") or "").strip())
        asset_fields = [(k, i, b, d) for k, rows in self.assets.items()
                        for i, fields in rows.items()
                        for b, d in fields.items()]
        asset_done = sum(1 for *_, d in asset_fields if d.strip())
        return {
            "ui": (ui_done, len(ui_fields)),
            "dialogue": (dialogue_done, dialogue_total),
            "assets": (asset_done, len(asset_fields)),
        }


# --------------------------------------------------------------------------
# patch routines
# --------------------------------------------------------------------------

def patch_text_table(table, table_name: str, translations: Translations) -> bool:
    changed = False

    language_id = swc.table_language_id(table)
    if language_id is None:
        language_id = swc.ensure_table_language(table)
        changed = True

    for field in table.m_fieldValues:
        value = translations.ui_value(table_name, field.m_fieldName)
        if value is None:
            value = ""          # leave untranslated -> English fallback
        if swc.set_field_language(field, language_id, value):
            changed = True

    # "language_option_uk" is a synthetic entry created by extract.py
    default_label = translations.ui_default(table_name, "language_option_uk")
    if default_label is not None:
        fields = swc.text_table_fields(table)
        if "language_option_uk" not in fields and table.m_fieldValues:
            uk_label = translations.ui_value(table_name, "language_option_uk")
            uk_label = uk_label if uk_label else default_label
            template = table.m_fieldValues[0]
            new_field = swc.clone_typetree(template)
            new_field.m_fieldName = "language_option_uk"
            language_ids = [int(v) for v in table.m_languageValues]
            new_field.m_keys = language_ids
            # Show the native name in every language column.
            new_field.m_values = [
                uk_label if lang == language_id else default_label
                for lang in language_ids
            ]
            table.m_fieldKeys.append(int(table.m_nextFieldID))
            table.m_fieldValues.append(new_field)
            table.m_nextFieldID = int(table.m_nextFieldID) + 1
            changed = True

    return changed


def patch_dropdown(dropdown) -> bool:
    options_holder = getattr(dropdown, "m_Options", None)
    options = getattr(options_holder, "m_Options", None)
    if not options:
        return False
    if not any(str(getattr(o, "m_Text", "")) == "language_option_uk"
               for o in options):
        new_option = swc.clone_typetree(options[-1])
        new_option.m_Text = "language_option_uk"
        options.append(new_option)
        return True
    return False


def patch_database(database, translations: Translations) -> tuple[bool, int]:
    changed = False
    filled = 0

    for conversation in database.conversations:
        conversation_id = int(conversation.id)
        for entry in conversation.dialogueEntries:
            value = translations.dialogue.get((conversation_id, int(entry.id)), "")
            if value.strip():
                filled += 1
            field = swc.field_lookup(entry.fields, swc.LANGUAGE_CODE)
            if field is None:
                template = swc.field_lookup(entry.fields, "fr")
                if template is None:
                    template = next(
                        (f for f in entry.fields if getattr(f, "type", None) == 4),
                        None,
                    )
                if template is None:
                    template = entry.fields[0] if entry.fields else None
                if template is None:
                    continue
                field = swc.make_localization_field(template, swc.LANGUAGE_CODE, value)
                entry.fields.append(field)
                changed = True
            elif field.value != value:
                field.value = value
                changed = True

    for kind, collection in (
        ("actors", database.actors),
        ("items", database.items),
        ("locations", database.locations),
    ):
        wanted_by_id = translations.assets.get(kind, {})
        for asset in collection:
            wanted = wanted_by_id.get(int(asset.id))
            if not wanted:
                continue
            for base, value in wanted.items():
                title = f"{base} {swc.LANGUAGE_CODE}"
                field = swc.field_lookup(asset.fields, title)
                if field is None:
                    template = swc.field_lookup(asset.fields, f"{base} fr")
                    if template is None:
                        continue
                    asset.fields.append(
                        swc.make_localization_field(template, title, value)
                    )
                    changed = True
                elif field.value != value:
                    field.value = value
                    changed = True

    return changed, filled


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the modified bundles")
    parser.add_argument("--force", action="store_true",
                        help="patch even if a bundle changed since the backup")
    parser.add_argument("--translations", type=Path,
                        default=swc.TRANSLATIONS_DIR / swc.LANGUAGE_CODE)
    parser.add_argument("--bundle-dir", type=Path, default=swc.BUNDLE_DIR)
    parser.add_argument("--backup-dir", type=Path, default=swc.DEFAULT_BACKUP_DIR)
    parser.add_argument("--only", type=str, default=None,
                        help="only bundles whose name contains this text")
    parser.add_argument("--no-ui", action="store_true")
    parser.add_argument("--no-dialogue", action="store_true")
    parser.add_argument("--no-dropdown", action="store_true")
    parser.add_argument("--fonts", action="store_true",
                        help="replace the source TTFs with the prepared fonts "
                             "from translations/uk/fonts")
    parser.add_argument("--font-dir", type=Path, default=fonts.FONT_DIR,
                        help="folder with the prepared replacement fonts")
    args = parser.parse_args(argv)

    bundle_dir: Path = args.bundle_dir
    backup_dir: Path = args.backup_dir
    if not bundle_dir.is_dir():
        print(f"Bundle folder not found: {bundle_dir}", file=sys.stderr)
        return 2

    translations = Translations(
        args.translations,
        allow_missing=args.no_ui and args.no_dialogue,
    )
    stats = translations.stats()
    replacements = fonts.ReplacementFonts(args.font_dir) if args.fonts else None

    paths = swc.bundle_paths(bundle_dir)
    if args.only:
        paths = [p for p in paths if args.only in p.name]

    print(f"Game root     : {swc.GAME_ROOT}")
    print(f"Bundles       : {len(paths)}")
    print(f"Translations  : {args.translations}")
    print(f"Backups       : {backup_dir}")
    if replacements is not None:
        print(f"Fonts         : {args.font_dir}")
    print(f"Mode          : {'APPLY' if args.apply else 'DRY-RUN'}")
    print("Progress      : "
          f"UI {stats['ui'][0]}/{stats['ui'][1]}, "
          f"dialogue {stats['dialogue'][0]}/{stats['dialogue'][1]}, "
          f"assets {stats['assets'][0]}/{stats['assets'][1]}")
    if replacements is not None:
        replacements.report()
    print()

    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest = swc.Manifest(backup_dir / "manifest.json")

    changed_bundles = 0
    table_count = 0
    dropdown_count = 0
    database_count = 0
    font_count = 0
    dialogue_filled = 0
    skipped = 0

    for index, path in enumerate(paths):
        if index % 10 == 0:
            print(f"  processing {index + 1}/{len(paths)} ...", flush=True)

        backup_path = backup_dir / path.name
        record = manifest.get(path.name)

        if backup_path.is_file():
            current_sha = swc.file_sha256(path)
            allowed = True
            if record is not None:
                allowed = current_sha in (
                    record["original_sha256"], record["patched_sha256"]
                )
            if not allowed and not args.force:
                swc.warn(f"{path.name}: game file changed since the backup; "
                         f"skipped (use --force to re-backup and patch)")
                skipped += 1
                continue
            if not allowed and args.force:
                swc.warn(f"{path.name}: --force, replacing the backup")
                swc.copy_with_dirs(path, backup_path)
                manifest.put(path.name, swc.file_sha256(path), "")
                record = manifest.get(path.name)
            source = backup_path
        else:
            source = path

        env = swc.load_bundle(source)
        dirty = []
        bundle_changed = False
        bundle_tables = 0
        bundle_dropdowns = 0
        bundle_databases = 0
        bundle_fonts = 0
        font_behaviours = []

        for behaviour in swc.iter_monobehaviours(env):
            class_name = swc.script_class(behaviour)
            if class_name == "TextTable" and not args.no_ui:
                name = str(getattr(behaviour, "m_Name", ""))
                if patch_text_table(behaviour, name, translations):
                    dirty.append(behaviour)
                    bundle_changed = True
                    bundle_tables += 1
            elif class_name == "TMP_Dropdown" and not args.no_dropdown:
                options = getattr(getattr(behaviour, "m_Options", None),
                                  "m_Options", None)
                if not options:
                    continue
                if not any(str(getattr(o, "m_Text", "")).startswith(
                        "language_option_") for o in options):
                    continue
                if patch_dropdown(behaviour):
                    dirty.append(behaviour)
                    bundle_changed = True
                    bundle_dropdowns += 1
            elif class_name == "DialogueDatabase" and not args.no_dialogue:
                database_changed, filled = patch_database(behaviour, translations)
                dialogue_filled += filled
                if database_changed:
                    dirty.append(behaviour)
                    bundle_changed = True
                    bundle_databases += 1
            elif args.fonts and fonts.is_font_asset(behaviour):
                font_behaviours.append(behaviour)

        if args.fonts and font_behaviours:
            for font in fonts.reorder_font_fallbacks(font_behaviours):
                dirty.append(font)
                bundle_changed = True
                bundle_fonts += 1

        if args.fonts:
            for font in fonts.patch_source_fonts(env, replacements):
                dirty.append(font)
                bundle_changed = True
                bundle_fonts += 1

        if not bundle_changed:
            del env
            continue

        changed_bundles += 1
        table_count += bundle_tables
        dropdown_count += bundle_dropdowns
        database_count += bundle_databases
        font_count += bundle_fonts

        if not args.apply:
            del env
            continue

        if not backup_path.is_file():
            swc.copy_with_dirs(path, backup_path)
            original_sha = swc.file_sha256(backup_path)
        else:
            original_sha = (record or {}).get("original_sha256") or \
                swc.file_sha256(backup_path)

        for behaviour in dirty:
            behaviour.save()
        swc.save_bundle(env, path)
        del env

        manifest.put(path.name, original_sha, swc.file_sha256(path))
        manifest.save()

    manifest.save()

    print()
    print(f"Bundles changed    : {changed_bundles}")
    print(f"  TextTables       : {table_count}")
    print(f"  Language dropdown: {dropdown_count}")
    print(f"  Databases        : {database_count}")
    if args.fonts:
        print(f"  Fonts            : {font_count}")
    if args.no_dialogue or args.no_ui:
        print(f"Dialogue strings   : {dialogue_filled}")
    if skipped:
        print(f"Skipped            : {skipped}")
    if not args.apply:
        print()
        print("Dry-run only - nothing was written.  Re-run with --apply.")
    else:
        print()
        print("Done.  Bundles were backed up to:")
        print(f"  {backup_dir}")
        print("Next: patch the assembly, then verify:")
        print("  dotnet run --project tools\\AssemblyPatcher -c Release -- --in-place")
        print("  python tools\\verify.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
