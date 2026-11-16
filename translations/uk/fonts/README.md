# Replacement fonts

Drop the prepared fonts in this folder, then run:

```bat
python tools\apply.py --fonts            (preview)
python tools\apply.py --fonts --apply    (writes the bundles)
```

`run.cmd apply` also picks them up, because it passes `--fonts`.

A file replaces the in-game **Font** asset whose name matches the file name
(without the extension, case-insensitive). `NotoSansJP-Regular.ttf` replaces
`NotoSansJP-Regular`, and so on. If the file has a different name, add a
`fonts.json` next to it:

```json
{
  "NotoSansJP-Regular": "NotoSansCJKjp-Regular.otf"
}
```

## Fonts to prepare

These six are the **source TTFs of dynamic TMP font assets**. They are the only
fonts the game rasterises at runtime, so replacing them is enough to change the
Cyrillic glyphs.

| File to provide | Original size | Used as the fallback of |
|---|---:|---|
| `NotoSansJP-Regular.ttf` | 5.7 MB | `Geo-Regular SDF`, `Trispace-Regular SDF` |
| `NotoSansTC-Regular.ttf` | 7.1 MB | `Geo-Regular SDF`, `Trispace-Regular SDF` |
| `NotoSansSC-Regular.ttf` | 10.6 MB | `Geo-Regular SDF`, `Trispace-Regular SDF` |
| `NotoSerifJP-Regular.ttf` | 8.0 MB | `NewRocker-Regular SDF` |
| `NotoSerifTC-Regular.ttf` | 10.0 MB | `NewRocker-Regular SDF` |
| `NotoSerifSC-Regular.ttf` | 14.8 MB | `NewRocker-Regular SDF` |

`LiberationSans.ttf` is optional: the shipped copy already contains the full
Ukrainian alphabet. Replace it only if you want a different look for text that
uses the built-in Unity font.

### Requirements

* **Keep the CJK coverage.** The originals are Noto Sans/Serif CJK JP/TC/SC
  subsets. A replacement that only has Latin + Cyrillic will break Chinese and
  Japanese text. Use the full Noto Sans CJK / Noto Serif CJK variants (or a
  font that also covers the same CJK range).
* **Contain the Ukrainian letters** `і ї є ґ І Ї Є Ґ`. The apply step reports
  which letters are missing and the verify step fails if a dynamic font cannot
  draw them.
* Prefer the same Noto CJK family. The apply step warns when the replacement's
  `unitsPerEm` differs from the original, because TMP keeps the line metrics
  baked into the font asset.
* TTF or OTF, any `unitsPerEm`; TMP reads the glyph metrics from the file.

## Fonts that cannot be replaced this way

These are **static** TMP assets: their glyphs are baked into an atlas texture,
so replacing the TTF has no effect. They contain no Cyrillic and draw it
through the Noto fallbacks above:

| Static asset | Cyrillic supplied by |
|---|---|
| `Geo-Regular SDF` | `NotoSansJP-Regular SDF (Geo)` → Sans JP/TC/SC |
| `NewRocker-Regular SDF` | `NotoSerifJP-Regular SDF (New Rocker)` → Serif JP/TC/SC |
| `Trispace-Regular SDF` | `NotoSansJP-Regular SDF (Trispace)` → Sans JP/TC/SC |
| `SWC-DamageNumbers` | Serif JP/TC/SC (damage numbers only) |
| `Blood-Gore` | no text |

If you want the *display* style itself for Cyrillic, a new TMP font asset would
have to be generated in Unity; a TTF replacement is not enough.

## Verify

```bat
python tools\verify.py
```

The `Font coverage` section lists every dynamic source font, the fallback chain
of each display font, and which font actually supplies Cyrillic. A missing
letter is reported as `MISSING і/ї/є/ґ`.
