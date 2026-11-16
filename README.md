# Ukrainian localization for *Sorry We're Closed*

Tools that add **Українська** to the in-game language menu (7th entry, index
`6`, language code `uk`) and write Ukrainian text into the game's Addressables
bundles.

The patch is reversible: original bundle bytes are copied to `_uk_backup/`, and
the original assembly to
`Sorry We're Closed_Data/Managed/Assembly-CSharp.dll.uk_backup`.

---

## Requirements

| What | Why | Install |
| --- | --- | --- |
| Python 3.10+ | runs the scripts | <https://www.python.org/downloads/> |
| `UnityPy` >= 1.20 | reads/writes Unity bundles | `python -m pip install -r requirements.txt` |
| `fontTools` | validates replacement fonts | included in `requirements.txt` |
| .NET 8 SDK | builds the IL patcher (language menu) | <https://dotnet.microsoft.com/download> |

Run everything from the game folder. **Close the game first** — the apply step
rewrites files inside the installation. A full run takes roughly 10–30 minutes
because all 152 Addressables bundles are scanned.

---

## Quick start

```bat
run.cmd extract     :: write translations\uk\*.json (read-only)
                    :: translate the "uk" values
run.cmd apply       :: patch bundles + assembly, then verify
run.cmd verify      :: re-check a patched installation
run.cmd restore     :: put the original files back
```

Then start the game → **Options → Language → Українська**.

Applying is safe to repeat: every run starts from the pristine backup, so no
duplicated fields are ever created. You can translate a little, apply, play,
translate more, apply again.

`run.cmd apply` is the same as:

```bat
python tools\apply.py --fonts --apply
dotnet run --project tools\AssemblyPatcher -c Release -- --in-place
python tools\verify.py
```

---

## Repository layout

```
run.cmd                     one entry point: extract / apply / restore / verify
requirements.txt
tools/
  extract.py                export translatable strings to JSON
  apply.py                  write the JSON into the bundles
  restore.py                copy the backup bundles (and DLL) back
  verify.py                 structural + font + assembly check
  fonts.py                  source-TTF replacement helpers
  lib_swc.py                shared bundle / TextTable / manifest helpers
  AssemblyPatcher/          C# IL patcher for the language menu
translations/uk/
  ui_text.json              menus, buttons, prompts
  dialogue.json             dialogue lines
  assets.json               actor / item / location names
  meta.json                 statistics about the scanned build (do not edit)
  fonts/                    optional replacement TTFs + fonts.json
```

`_uk_backup/` is created by the first apply and is not part of the repository.

---

## The translation files

All files live in `translations/uk/`.

| File | Contents |
| --- | --- |
| `ui_text.json` | every `TextTable` string: menus, buttons, prompts |
| `dialogue.json` | every dialogue line, grouped by conversation |
| `assets.json` | actor / item / location names and descriptions |
| `meta.json` | statistics about the scanned game build (do not edit) |

Rules:

* Only edit the `"uk"` values. Leave `"en"`, `id`, table and field names alone.
* An empty `"uk"` value is **not** an error: the game falls back to English for
  that string, so a half-finished file works fine.
* Keep valid JSON (no trailing commas). A broken file stops the apply step with
  an error naming the file.
* `dialogue.json` has the shape

  ```json
  {
    "conversations": [
      {
        "id": 1,
        "title": "…",
        "entries": [
          { "id": 5, "speaker": "Michelle", "en": "Hello.", "uk": "Привіт." }
        ]
      }
    ]
  }
  ```

  `speaker` is only a hint for the translator — the game does not read it.
* `language_option_uk` in `ui_text.json` is the label shown in the language
  dropdown; it is already filled with `Українська`.

Translate `dialogue.json` in whatever tool you like, then keep the structure
intact: each entry has an `id` and a `uk` value, and the markup tags /
placeholders must match the English source. `apply.py` only reads the finished
file; it does not create or merge partial work.

---

## What the patch changes

*Every* copy of the relevant asset is patched (the game stores the same data in
many bundles):

* `TextTable` → adds language key `uk`, a numeric language id, and one `uk`
  column value per field. Adds a synthetic `language_option_uk` entry to the
  *Settings Menu* table.
* Language `TMP_Dropdown` → appends a `language_option_uk` option after the
  Simplified Chinese one.
* `DialogueDatabase` → adds a `uk` localization field to every dialogue entry
  and a `… uk` field for actor/item/location names.
* Source fonts → replaces the six dynamic Noto CJK TTFs (see below).
* `Assembly-CSharp.dll` → two small IL edits in `LanguageSettings`:
  * `LanguageChange()`: `if (languageSettings.language == 6) DialogueManager.SetLanguage("uk");`
  * `GetDefaultLanguage()`: `SystemLanguage.Ukrainian → 6` (first launch on a
    Ukrainian Windows picks Ukrainian automatically).

Existing languages (including Simplified Chinese) are untouched.

Game files touched:
`Sorry We're Closed_Data\StreamingAssets\aa\StandaloneWindows64\*.bundle`
and `Sorry We're Closed_Data\Managed\Assembly-CSharp.dll`.

---

## Fonts

The display fonts (`Geo-Regular SDF`, `NewRocker-Regular SDF`,
`Trispace-Regular SDF`, `SWC-DamageNumbers`) are **static atlases** without
Cyrillic; they draw it through the dynamic Noto fallbacks. Only the six dynamic
source TTFs can be replaced:

`NotoSansJP-Regular`, `NotoSansTC-Regular`, `NotoSansSC-Regular`,
`NotoSerifJP-Regular`, `NotoSerifTC-Regular`, `NotoSerifSC-Regular`.

Put a Cyrillic version of each into `translations\uk\fonts\` using the same
name (`NotoSansJP-Regular.ttf`, …). An optional `fonts.json` maps an asset name
to a differently named file:

```json
{ "NotoSansJP-Regular": "NotoSansCJKjp-Regular.otf" }
```

`run.cmd apply` passes `--fonts` automatically. To replace only the fonts:

```bat
python tools\apply.py --fonts           (preview)
python tools\apply.py --fonts --apply   (writes bundles, backs them up)
```

A replacement must keep the font's CJK coverage, otherwise Chinese/Japanese
text breaks. The apply step warns when a replacement drops CJK glyphs or
changes `unitsPerEm`. See `translations\uk\fonts\README.md` for the full list.

---

## Restoring

```bat
run.cmd restore
```

copies `_uk_backup\*.bundle` and `Assembly-CSharp.dll.uk_backup` back. A
full backup needs roughly as much space as the modified bundles (~1.5 GB).
Steam → *Verify integrity of game files* also reverts everything.

**After a game update** the bundles are replaced, so run `run.cmd apply` again
(`run.cmd extract` first if the text itself changed).

---

## Command-line reference

```bat
python tools\extract.py [--bundle-dir DIR] [--out DIR]
python tools\apply.py [--apply] [--only NAME] [--force]
                      [--fonts] [--font-dir DIR]
                      [--no-ui] [--no-dialogue] [--no-dropdown]
                      [--translations DIR] [--bundle-dir DIR] [--backup-dir DIR]
python tools\restore.py [--assembly] [--bundle-dir DIR] [--backup-dir DIR]
python tools\verify.py [--bundle-dir DIR] [--check-assembly]
dotnet run --project tools\AssemblyPatcher -c Release -- --in-place
dotnet run --project tools\AssemblyPatcher -c Release -- --check
dotnet run --project tools\AssemblyPatcher -c Release -- --restore
```

`apply.py` without `--apply` is a dry run: it reports the same counters but
writes nothing. `--only NAME` limits the work to bundles whose file name
contains `NAME` (useful for tests). `--force` re-backs-up bundles that changed
after the first run.

---

## Troubleshooting

**`і`, `ї`, `є`, `ґ` appear as empty boxes.**
The replacement fonts are missing the letters. Check the `Font coverage`
section of `python tools\verify.py`; it lists every dynamic source font and
which font actually supplies Cyrillic for each display font.

**The menu shows `language_option_uk` as literal text.**
The Settings Menu `TextTable` was not patched — run `run.cmd apply` again and
check the verify output.

**The game still uses English after choosing Українська.**
`Assembly-CSharp.dll` was not patched (Steam update? wrong install?). Run
`dotnet run --project tools\AssemblyPatcher -c Release -- --check`.

**Chinese/Japanese text broke.**
The replacement fonts have no CJK glyphs. Restore with `run.cmd restore`, then
use Noto Sans CJK / Noto Serif CJK files (they include Cyrillic).
