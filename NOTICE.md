# Notices and disclaimer

**This is an unofficial, fan-made Ukrainian localization.** It is not
affiliated with, endorsed by, or supported by **à la mode games** (developer)
or **Akupara Games** (publisher). *Sorry We're Closed* and all of its game
content, text, art, audio and code are © à la mode games. All rights reserved
by their respective owners.

> Це неофіційний фанатський переклад. Він не пов'язаний з à la mode games чи
> Akupara Games і не схвалений ними. Усі права на гру та її вміст належать
> відповідним правовласникам.

## Credits

*Sorry We're Closed* — developed by [à la mode games](https://alamode.games),
published by [Akupara Games](https://www.akuparagames.com/).

## What this repository contains

| Part | License / status |
|---|---|
| `tools/`, `run.cmd`, `tools/AssemblyPatcher/` | MIT — see `LICENSE` |
| `translations/uk/*.json` (Ukrainian strings) | © the translation contributors. The translation is a derivative of the game's script; it is shared for use with a legitimately owned copy of the game and grants no rights to the underlying work. |
| `translations/uk/fonts/NotoSans-Regular.ttf`, `NotoSerif-Regular.ttf` | SIL Open Font License 1.1 — see `translations/uk/fonts/OFL.txt` |

The repository **does not contain game binaries**. The English source strings
are not published either: `run.cmd extract` regenerates them locally from your
own copy of the game.

## Third-party software

The tools depend on these libraries at runtime; they are installed separately
and are not vendored in this repository.

* [UnityPy](https://github.com/K0lb3/UnityPy) — MIT
* [fontTools](https://github.com/fonttools/fonttools) — MIT
* [Mono.Cecil](https://github.com/jbevain/cecil) — MIT

## Trademarks

*Sorry We're Closed*, its logo and the names of its characters are trademarks
or copyrighted material of their owners. They are used here only to describe
what this localization is for (nominative use). No endorsement is implied.

## Distribution of patched game files

Patched `.bundle` files and a patched `Assembly-CSharp.dll` are **not**
distributed with this repository. Building them locally for personal use is
what `run.cmd apply` does. Publishing ready-made patched binaries requires
permission from the rights holder; see the installation section of the
top-level `README.md` for the current status.
