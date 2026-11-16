"""Verify the Ukrainian patch: bundles, fonts and (optionally) the assembly.

    python tools\\verify.py
    python tools\\verify.py --check-assembly
    python tools\\verify.py --bundle-dir <folder>

The script only reads files.  Exit code 0 means every structural check passed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import fonts
import lib_swc as swc

FALLBACK_FONT = "LiberationSans SDF - Fallback"
DISPLAY_FONTS = ("Geo-Regular SDF", "NewRocker-Regular SDF", "Trispace-Regular SDF")
NOTO_SOURCES = (
    "NotoSansJP-Regular", "NotoSansTC-Regular", "NotoSansSC-Regular",
    "NotoSerifJP-Regular", "NotoSerifTC-Regular", "NotoSerifSC-Regular",
)


def check_font_coverage(bundle_dir: Path) -> bool:
    """Check that every dynamic font used for Cyrillic has the letters.

    The display fonts (`Geo-Regular SDF`, `NewRocker-Regular SDF`,
    `Trispace-Regular SDF`) are static atlases without Cyrillic.  Their text is
    drawn by the first dynamic fallback that covers the Ukrainian alphabet, so
    that source TTF is the one that must contain the letters.
    """
    print("Font coverage")

    source_fonts: dict[int, dict] = {}   # Font path_id -> {name, data, bundle}
    assets: dict[int, dict] = {}         # TMP asset path_id -> metadata
    name_by_id: dict[int, str] = {}

    for path in swc.bundle_paths(bundle_dir):
        env = swc.load_bundle(path)
        for obj in env.objects:
            if obj.type.name == "Font":
                try:
                    font = obj.read()
                except Exception:
                    continue
                data = bytes(getattr(font, "m_FontData", b"") or b"")
                source_fonts[obj.path_id] = {
                    "name": str(getattr(font, "m_Name", "")),
                    "data": data,
                    "bundle": path.name,
                }
                name_by_id[obj.path_id] = source_fonts[obj.path_id]["name"]
            elif obj.type.name == "MonoBehaviour":
                try:
                    data = obj.read()
                except Exception:
                    continue
                name = str(getattr(data, "m_Name", "") or "")
                if name:
                    name_by_id.setdefault(obj.path_id, name)
                if not fonts.is_font_asset(data):
                    continue
                table = getattr(data, "m_CharacterTable", None)
                source = getattr(data, "m_SourceFontFile", None)
                assets[obj.path_id] = {
                    "name": name,
                    "bundle": path.name,
                    "mode": int(getattr(data, "m_AtlasPopulationMode", 0)),
                    "source": int(getattr(source, "m_PathID", 0)) if source else 0,
                    "fallbacks": [
                        int(getattr(p, "m_PathID", 0))
                        for p in (getattr(data, "m_FallbackFontAssetTable", None) or [])
                    ],
                    "chars": (
                        {int(c.m_Unicode) for c in table if hasattr(c, "m_Unicode")}
                        if table else None
                    ),
                }
        del env

    parsed: dict[int, dict] = {}
    warned_fonttools = False

    def stats(path_id: int) -> dict | None:
        nonlocal warned_fonttools
        info = source_fonts.get(path_id)
        if info is None or not info["data"]:
            return None
        if path_id not in parsed:
            parsed[path_id] = fonts.inspect_ttf(info["data"])
            if not parsed[path_id] and not warned_fonttools:
                swc.warn("fontTools is not installed; cannot inspect the TTFs")
                warned_fonttools = True
        return parsed[path_id]

    def ttf_covers(path_id: int) -> bool:
        info = stats(path_id)
        if info is None:
            return False
        missing = info.get("missing")
        return True if missing is None else not missing

    def supplier(asset_id: int, seen: set[int] | None = None) -> str | None:
        """Name of the first font in a chain that can draw the letters."""
        seen = set() if seen is None else seen
        if asset_id in seen:
            return None
        seen.add(asset_id)
        asset = assets.get(asset_id)
        if asset is None:
            return None
        if asset["mode"] == 1:
            return asset["name"] if ttf_covers(asset["source"]) else None
        table = asset["chars"]
        if table and all(ord(c) in table for c in fonts.UKRAINIAN_GLYPHS):
            return asset["name"]
        for pid in asset["fallbacks"]:
            found = supplier(pid, seen)
            if found:
                return found
        return None

    ok = True

    # Dynamic TMP assets rasterise missing characters from their source TTF.
    dynamic: dict[int, set[str]] = {}
    for asset in assets.values():
        if asset["mode"] == 1 and asset["source"]:
            dynamic.setdefault(asset["source"], set()).add(asset["name"])

    print("  Dynamic font sources")
    missing_sources: list[str] = []
    for path_id, users in sorted(
            dynamic.items(),
            key=lambda item: source_fonts.get(item[0], {}).get("name", "")):
        info = source_fonts.get(path_id)
        if info is None:
            ok = False
            swc.warn(f"source font {path_id} not found "
                     f"(used by {', '.join(sorted(users))})")
            continue
        good = ttf_covers(path_id)
        if not good:
            ok = False
            missing_sources.append(info["name"])
        parsed_info = stats(path_id) or {}
        cjk = parsed_info.get("cjk")
        if info["name"] in NOTO_SOURCES and cjk is not None and cjk < 1000:
            swc.warn(f"'{info['name']}' has only {cjk} CJK glyphs - Japanese/"
                     f"Chinese text will break (accepted: Cyrillic-only font)")
        status = "ok" if good else "MISSING і/ї/є/ґ"
        cjk_text = f"{cjk:>6,} CJK" if cjk is not None else "     ? CJK"
        print(f"    {info['name']:26s} {info['bundle'][:12]}  "
              f"{cjk_text}  {status}")

    # Static display fonts: report which fallback actually supplies Cyrillic.
    print("  Display font chains")
    checked_any = False
    for asset in assets.values():
        if asset["name"] not in DISPLAY_FONTS:
            continue
        checked_any = True
        chain = [name_by_id.get(pid, f"<{pid}>") for pid in asset["fallbacks"]]
        source_name = None
        for pid in asset["fallbacks"]:
            source_name = supplier(pid)
            if source_name:
                break
        if source_name is None:
            ok = False
            print(f"    {asset['name']:24s} -> {', '.join(chain) or '(none)'}"
                  f"  [NO CYRILLIC]")
            continue
        print(f"    {asset['name']:24s} -> {', '.join(chain)}")
        print(f"      Cyrillic from: {source_name}")
        if source_name == FALLBACK_FONT:
            swc.warn(f"{asset['name']}: Cyrillic comes from '{FALLBACK_FONT}' "
                     f"(built-in LiberationSans look)")

    if not checked_any:
        swc.warn("no display fonts found (unexpected)")

    if missing_sources:
        swc.warn("prepare Cyrillic versions and put them in "
                 "translations\\uk\\fonts\\:")
        for name in sorted(set(missing_sources)):
            swc.warn(f"  {name}.ttf")
        swc.warn("then re-run: python tools\\apply.py --fonts --apply")

    liberation_pid = next(
        (pid for pid, f in source_fonts.items() if f["name"] == "LiberationSans"),
        None)
    if liberation_pid is not None:
        if ttf_covers(liberation_pid):
            print("  LiberationSans contains the full Ukrainian alphabet")
        else:
            ok = False
            swc.warn("LiberationSans is missing Ukrainian letters")

    if not ok:
        swc.warn("If the game shows boxes for і/ї/є/ґ, run: "
                 "python tools\\apply.py --fonts --apply")
    print()
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=swc.BUNDLE_DIR)
    parser.add_argument("--check-assembly", action="store_true")
    parser.add_argument("--project", type=Path,
                        default=swc.TOOLS_DIR / "AssemblyPatcher")
    args = parser.parse_args(argv)

    if not args.bundle_dir.is_dir():
        print(f"Bundle folder not found: {args.bundle_dir}", file=sys.stderr)
        return 2

    paths = swc.bundle_paths(args.bundle_dir)
    print(f"Checking {len(paths)} bundles in {args.bundle_dir}")
    print()

    problems: list[str] = []
    tables_seen = 0
    tables_ok = 0
    tables_with_uk = 0
    language_option_ok = 0
    language_option_expected = 0
    dropdowns_seen = 0
    dropdowns_ok = 0
    databases_seen = 0
    entries_seen = 0
    entries_with_uk = 0
    entries_translated = 0
    assets_translated = 0

    for index, path in enumerate(paths):
        if index % 10 == 0:
            print(f"  checking {index + 1}/{len(paths)} ...", flush=True)
        env = swc.load_bundle(path)
        for behaviour in swc.iter_monobehaviours(env):
            class_name = swc.script_class(behaviour)
            if class_name == "TextTable":
                tables_seen += 1
                name = str(getattr(behaviour, "m_Name", ""))
                language_id = swc.table_language_id(behaviour)
                if language_id is None:
                    problems.append(f"{path.name}: TextTable '{name}' has no 'uk' language")
                    continue
                tables_with_uk += 1
                fields = list(behaviour.m_fieldValues)
                missing = [f.m_fieldName for f in fields
                           if language_id not in list(f.m_keys)]
                if missing:
                    problems.append(
                        f"{path.name}: TextTable '{name}' - "
                        f"{len(missing)} field(s) without a uk entry"
                    )
                else:
                    tables_ok += 1
                if name.lower() == "settings menu":
                    language_option_expected += 1
                    option = next((f for f in fields
                                   if f.m_fieldName == "language_option_uk"), None)
                    if option is None:
                        problems.append(
                            f"{path.name}: Settings Menu lacks language_option_uk"
                        )
                    else:
                        values = dict(zip(option.m_keys, option.m_values))
                        if str(values.get(0, "")).strip():
                            language_option_ok += 1
                        else:
                            problems.append(
                                f"{path.name}: language_option_uk is empty"
                            )
            elif class_name == "TMP_Dropdown":
                options = getattr(getattr(behaviour, "m_Options", None),
                                  "m_Options", None)
                if not options:
                    continue
                texts = [str(getattr(o, "m_Text", "")) for o in options]
                if not any(t.startswith("language_option_") for t in texts):
                    continue
                dropdowns_seen += 1
                if "language_option_uk" in texts:
                    dropdowns_ok += 1
                else:
                    problems.append(
                        f"{path.name}: language dropdown has no "
                        f"language_option_uk ({texts})"
                    )
            elif class_name == "DialogueDatabase":
                databases_seen += 1
                for conversation in behaviour.conversations:
                    for entry in conversation.dialogueEntries:
                        entries_seen += 1
                        field = swc.field_lookup(entry.fields, swc.LANGUAGE_CODE)
                        if field is not None:
                            entries_with_uk += 1
                            if str(field.value).strip():
                                entries_translated += 1
                for collection in (behaviour.actors, behaviour.items,
                                   behaviour.locations):
                    for asset in collection:
                        for field in asset.fields:
                            title = str(getattr(field, "title", ""))
                            if title.endswith(" uk") and str(field.value).strip():
                                assets_translated += 1
        del env

    print()
    print("Bundles")
    print(f"  TextTables with 'uk'      : {tables_with_uk}/{tables_seen}")
    print(f"  TextTables fully keyed    : {tables_ok}/{tables_seen}")
    print(f"  Settings menus w/ option  : {language_option_ok}/{language_option_expected}")
    print(f"  Language dropdowns patched: {dropdowns_ok}/{dropdowns_seen}")
    print(f"  Dialogue databases        : {databases_seen}")
    print(f"  Entries with uk field     : {entries_with_uk}/{entries_seen}")
    print(f"  Entries translated        : {entries_translated}")
    print(f"  Asset fields translated   : {assets_translated}")
    print()

    font_ok = check_font_coverage(args.bundle_dir)

    assembly_ok = True
    if args.check_assembly:
        print("Assembly")
        try:
            result = subprocess.run(
                ["dotnet", "run", "--project", str(args.project), "--", "--check"],
                capture_output=True, text=True, timeout=300,
            )
            print(result.stdout.rstrip())
            if result.returncode != 0:
                assembly_ok = False
                if result.stderr.strip():
                    print(result.stderr.rstrip())
        except Exception as exc:
            assembly_ok = False
            swc.warn(f"could not run AssemblyPatcher: {exc}")
        print()

    if problems:
        print(f"Problems ({len(problems)}):")
        for problem in problems[:40]:
            print(f"  - {problem}")
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")
        print()

    ok = not problems and font_ok and assembly_ok
    print("RESULT:", "OK" if ok else "PROBLEMS FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
