# Українська — translation files

These JSON files were exported from the game by `run.cmd extract`. Fill in the
`"uk"` values, then run `run.cmd apply` in the game folder.

## Files

| File | What to translate |
| --- | --- |
| `ui_text.json` | menus, buttons, settings, prompts — 426 strings in 7 TextTables. Grouped by table name, then by field name. |
| `dialogue.json` | 6290 dialogue lines in 820 conversations. Grouped by conversation; each entry has `speaker`, `en`, `uk`. |
| `assets.json` | 146 characters, 76 items and 262 locations (898 fields with names/descriptions). |
| `meta.json` | export statistics. **Do not edit** (ignored by the apply step). |

## Status

| File | Translated |
| --- | --- |
| `ui_text.json` | 425/426 (one intentionally empty prompt) |
| `assets.json` | 855/855 non-empty fields (43 fields are empty in English too) |
| `dialogue.json` | 6290/6290 (100%) |

## Ground rules

* Translate only the `"uk"` field. Do not change `"en"`, `id`, table names,
  field names or the JSON structure — the apply step looks text up by those.
* `"uk": ""` means *not translated yet*: the game shows the English text for
  that line. Nothing breaks, so translate at your own pace.
* Keep the file UTF-8 (with or without BOM is fine). Use a JSON-aware editor
  (VS Code, Notepad++, JSON Editor Online) to avoid broken commas/quotes.
* Newlines inside a string must be escaped as `\n`, quotes as `\"`.
* Placeholders such as `<color=...>`, `[var=...]`, `{0}`, `\n` and names in
  square brackets must be kept exactly as they are in the English text.
* `en` is a snapshot of the current English line, useful as reference. If the
  game gets updated, re-run `run.cmd extract` — it keeps existing `uk` values
  for lines that still exist (merge by conversation id + entry id).

## Glossary used in `ui_text.json`

Keep these consistent when translating `dialogue.json` and `assets.json`:

| English | Українська |
| --- | --- |
| Michelle | Мішель |
| Darrel | Даррел |
| Oakley | Оуклі |
| Chamuel | Чамуель |
| Robyn | Робін |
| Clarissa | Клариса |
| Benedict | Бенедикт |
| The Duchess | Герцогиня |
| Dream Eater | Пожирачка снів |
| Third Eye | Третє око |
| Heartbreak / Heartbreaker | Серцеїд |
| Hellhound (pistol) | Пекельний гончак |
| Hellfire (shotgun) | Пекельне полум'я |
| Devil's Maw (axe) | Паща диявола |
| Logbook | Журнал |
| Yowza / Yowzas | Йовза / Йовзи (у реченнях: йовзу / йовз) |
| Artifacts | Артефакти |
| Upgrades | Покращення |
| Time Attack | Випробування на час |
| New Game+ | Нова гра+ |
| Her Royal Deadness | Її Королівська Мертвість |
| Mimi the Conqueror | Мімі Завойовниця |

## Order of work that feels best

1. `ui_text.json` → the settings menu and the language dropdown (quick win).
2. `dialogue.json` → conversation by conversation; each entry has its speaker.
3. `assets.json` → names shown in the journal/inventory.

## Checking progress

`run.cmd apply` prints how many UI strings / dialogue lines / asset fields are
filled, e.g.

```
Progress : UI 0/426, dialogue 0/6290, assets 0/898
```

Only filled values are written as Ukrainian; empty ones fall back to English.

## Game files changed or added

### Changed by `run.cmd apply`

| Path (relative to the game folder) | Change |
| --- | --- |
| `Sorry We're Closed_Data\StreamingAssets\aa\StandaloneWindows64\*.bundle` | 86 of the 152 Addressables bundles receive the `uk` language column, the extra language-dropdown option, the dialogue/asset translations and the prepared source fonts. The exact file names are listed in `_uk_backup\manifest.json`. |
| `Sorry We're Closed_Data\Managed\Assembly-CSharp.dll` | Two IL edits in `LanguageSettings`: dropdown index 6 calls `DialogueManager.SetLanguage("uk")`, and a Ukrainian system locale selects index 6 on first launch. |

Nothing else in the game folder is modified. `Sorry We're Closed_Data\data.unity3d`
is only read: it supplies the built-in `LiberationSans` TTF that the verify
step inspects.

### Added for the translation and rollback

| Path | Contents |
| --- | --- |
| `translations\uk\` | Translation source: `ui_text.json`, `dialogue.json`, `assets.json`, `meta.json` and this README. |
| `translations\uk\fonts\` | Optional Cyrillic replacements for the six dynamic game fonts; see `fonts\README.md`. |
| `tools\` | `extract.py`, `apply.py`, `restore.py`, `verify.py`, `lib_swc.py`, `fonts.py` and `AssemblyPatcher\`. |
| `run.cmd` | One entry point: `extract`, `apply`, `restore`, `verify`. |
| `_uk_backup\` | Pristine copies of the 86 patched bundles plus `manifest.json` (original and patched SHA-256). Used by `run.cmd restore`; also what makes repeated applies safe. |
| `Sorry We're Closed_Data\Managed\Assembly-CSharp.dll.uk_backup` | Original assembly, created next to the DLL on the first patch. |

### Sharing the translation

* **Recommended:** share `translations\uk\`, `tools\`, `run.cmd` and
  `requirements.txt`. The recipient drops them into their own game folder and
  runs `run.cmd apply`. It rebuilds everything from their own untouched files,
  so it works with any copy of the same game version. They need Python with
  `UnityPy` and `fontTools`, plus the .NET 8 SDK (see the top-level `README.md`).
* **Drop-in only:** you can also share the 86 patched `.bundle` files and the
  patched `Assembly-CSharp.dll`, copied over the same paths. This only works for
  the exact same game build: bundle names are content hashes, and a different
  build may use different names or contents. Never mix bundles from two builds.
* Do **not** include `_uk_backup\` in a drop-in package; it is only needed to
  restore or re-apply on the machine that created it. Keep your own copy.

## Translating

The JSON files are plain text and can be edited in any external tool. Keep the
existing structure: `ui_text.json` and `assets.json` use `{ "uk": "..." }`
values, `dialogue.json` uses `conversations[].entries[]` with `id` and `uk`, and
markup tags / placeholders must stay identical to the English source.
`apply.py` reads the finished files and does not merge partial work.

## Fonts

The game's display fonts (`Geo-Regular SDF`, `NewRocker-Regular SDF`,
`Trispace-Regular SDF`) are static atlases without Cyrillic; they draw it
through the dynamic Noto fallbacks. The Cyrillic glyphs therefore come from six
replaceable source TTFs:

`NotoSansJP-Regular`, `NotoSansTC-Regular`, `NotoSansSC-Regular`,
`NotoSerifJP-Regular`, `NotoSerifTC-Regular`, `NotoSerifSC-Regular`.

Put a Cyrillic version of each (keeping its CJK coverage) into
`translations\uk\fonts\` and run `python tools\apply.py --fonts --apply`, or
simply `run.cmd apply`. See `translations\uk\fonts\README.md` for the naming
rules and the optional `fonts.json` mapping. If the letters show as empty
boxes, check the `Font coverage` section of `python tools\verify.py`.
