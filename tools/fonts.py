"""Font replacement for the Ukrainian patch.

The six replaceable fonts are the dynamic Noto CJK source TTFs.  The static
display fonts (Geo / NewRocker / Trispace) keep their baked atlas and draw
Cyrillic through those Noto fallbacks, so only the source TTFs are swapped.

A file is matched to the in-game Font asset by name; see
`translations/uk/fonts/README.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

import lib_swc as swc

UKRAINIAN_GLYPHS = "\u0456\u0457\u0454\u0491\u0406\u0407\u0404\u0490"  # іїєґІЇЄҐ
FONT_SUFFIXES = (".ttf", ".otf")
FONT_DIR = swc.TRANSLATIONS_DIR / swc.LANGUAGE_CODE / "fonts"

# CJK / kana / hangul blocks.  The replaceable fonts are Noto CJK faces used as
# fallbacks for the Japanese and Chinese languages, so a replacement that drops
# this coverage breaks those languages.
CJK_RANGES = (
    (0x3040, 0x30FF),   # hiragana + katakana
    (0x3400, 0x4DBF),   # CJK unified ideographs extension A
    (0x4E00, 0x9FFF),   # CJK unified ideographs
    (0xF900, 0xFAFF),   # CJK compatibility ideographs
    (0xAC00, 0xD7AF),   # hangul syllables
)

# TMP assets that belong to the built-in LiberationSans family.  A static
# display font usually lists `LiberationSans SDF` first, and that asset has its
# own dynamic `LiberationSans SDF - Fallback`.  TMP can resolve that nested
# chain before the Noto fonts, so Cyrillic ends up in LiberationSans instead of
# the prepared font.  Moving these two pointers to the end of the list lets the
# Noto fallbacks win.
LIBERATION_SANS_PATHS = {-7997044049995672069, 1226172976683833684}


def cjk_glyph_count(cmap: dict) -> int:
    return sum(1 for cp in cmap
               if any(start <= cp <= end for start, end in CJK_RANGES))


def is_font_asset(behaviour) -> bool:
    """TMP_FontAsset is a MonoBehaviour with an external script class."""
    return (hasattr(behaviour, "m_CharacterTable")
            and hasattr(behaviour, "m_FallbackFontAssetTable")
            and hasattr(behaviour, "m_AtlasPopulationMode"))


def has_ukrainian_glyphs(font) -> bool:
    table = getattr(font, "m_CharacterTable", None)
    if not table:
        return False
    codepoints = {int(c.m_Unicode) for c in table if hasattr(c, "m_Unicode")}
    return all(ord(char) in codepoints for char in UKRAINIAN_GLYPHS)


def inspect_ttf(data: bytes) -> dict:
    """Parse a TTF/OTF and report its coverage.

    Returns ``{}`` when fontTools is not installed, so the file is accepted
    without validation.
    """
    try:
        import io
        from fontTools.ttLib import TTFont
    except ImportError:
        return {}
    try:
        font = TTFont(io.BytesIO(data), lazy=True)
        cmap = font.getBestCmap() or {}
        info = {
            "upem": int(font["head"].unitsPerEm),
            "glyphs": len(cmap),
            "cjk": cjk_glyph_count(cmap),
            "missing": [c for c in UKRAINIAN_GLYPHS if ord(c) not in cmap],
        }
        font.close()
        return info
    except Exception as exc:
        return {"error": str(exc)[:200]}


def reorder_font_fallbacks(fonts: list) -> list:
    """Move the LiberationSans fallbacks behind the Noto fonts.

    The display fonts are static and have no Cyrillic; they rely on a dynamic
    fallback.  Their original order starts with `LiberationSans SDF`, whose
    nested `LiberationSans SDF - Fallback` can answer first, making Cyrillic
    render in LiberationSans.  Putting the prepared Noto fonts first keeps the
    whole line in one font.
    """
    dirty = []
    for font in fonts:
        if int(getattr(font, "m_AtlasPopulationMode", 0)) == 1:
            continue
        if has_ukrainian_glyphs(font):
            continue
        existing = list(getattr(font, "m_FallbackFontAssetTable", None) or [])
        if not existing:
            continue
        kept = [p for p in existing
                if int(getattr(p, "m_PathID", 0)) not in LIBERATION_SANS_PATHS]
        moved = [p for p in existing
                 if int(getattr(p, "m_PathID", 0)) in LIBERATION_SANS_PATHS]
        if not moved or kept + moved == existing:
            continue
        font.m_FallbackFontAssetTable = kept + moved
        dirty.append(font)
        name = str(getattr(font, "m_Name", ""))
        swc.say(f"    font '{name}': Noto fallbacks moved before LiberationSans")
    return dirty


class ReplacementFonts:
    """Cyrillic-capable fonts prepared by the translator.

    A file is matched to the in-game Font asset by its name:
    ``NotoSansJP-Regular.ttf`` replaces the Font object named
    ``NotoSansJP-Regular``.  An optional ``fonts.json`` can map an asset name
    to a differently named file::

        {"NotoSansJP-Regular": "NotoSansCJKjp-Regular.otf"}

    Only the source TTF of a *dynamic* TMP font asset is read at runtime.
    """

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.fonts: dict[str, tuple[str, Path, bytes, dict]] = {}
        self.problems: list[str] = []
        self._load()

    def _candidates(self) -> dict[str, Path]:
        candidates: dict[str, Path] = {}
        manifest = self.directory / "fonts.json"
        if manifest.is_file():
            try:
                raw = json.loads(manifest.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                self.problems.append(f"{manifest.name}: {exc}")
                raw = {}
            if isinstance(raw, dict):
                for name, filename in raw.items():
                    if isinstance(filename, str):
                        candidates[str(name)] = self.directory / filename
        if self.directory.is_dir():
            mapped = {path.resolve() for path in candidates.values()}
            for path in sorted(self.directory.iterdir()):
                if path.suffix.lower() not in FONT_SUFFIXES:
                    continue
                if path.resolve() in mapped:
                    continue
                candidates.setdefault(path.stem, path)
        return candidates

    def _load(self) -> None:
        for name, path in self._candidates().items():
            if not path.is_file():
                self.problems.append(f"{path.name}: file not found")
                continue
            data = path.read_bytes()
            info = inspect_ttf(data)
            if info.get("error"):
                self.problems.append(f"{path.name}: {info['error']}")
                continue
            self.fonts[name.strip().casefold()] = (name, path, data, info)

    def get(self, name: str):
        return self.fonts.get(str(name).strip().casefold())

    def report(self) -> None:
        if not self.fonts and not self.problems:
            swc.say(f"    no replacement fonts in {self.directory}")
            return
        for _key, (name, path, data, info) in sorted(self.fonts.items()):
            missing = info.get("missing") or []
            note = ("  ! missing " + " ".join(missing)) if missing else ""
            swc.say(f"    {path.name:24s} -> '{name}'  "
                    f"({len(data):,} bytes, {info.get('glyphs', '?')} glyphs, "
                    f"{info.get('cjk', '?')} CJK)"
                    f"{note}")
        for problem in self.problems:
            swc.warn(problem)


def patch_source_fonts(env, replacements: ReplacementFonts) -> list:
    """Swap in the prepared TTF for every Font whose name matches a file."""
    dirty = []
    for obj in env.objects:
        if obj.type.name != "Font":
            continue
        try:
            font = obj.read()
        except Exception:
            continue
        name = str(getattr(font, "m_Name", ""))
        replacement = replacements.get(name)
        if replacement is None:
            continue
        _asset_name, path, data, info = replacement
        current = bytes(getattr(font, "m_FontData", b"") or b"")
        if current == data:
            continue
        if current and info.get("upem"):
            original = inspect_ttf(current)
            if original.get("upem") and original["upem"] != info["upem"]:
                swc.warn(f"font '{name}': replacement has upem {info['upem']}, "
                         f"original {original['upem']}; line metrics may differ")
            had = original.get("cjk", 0)
            now = info.get("cjk", 0)
            if had and now < had * 0.5:
                swc.warn(f"font '{name}': replacement has {now} CJK glyphs, "
                         f"the original had {had} - Japanese/Chinese text "
                         f"will break. Use a Noto Sans/Serif CJK face.")
        font.m_FontData = list(data)
        dirty.append(font)
        swc.say(f"    font '{name}' <- {path.name}")
    return dirty
