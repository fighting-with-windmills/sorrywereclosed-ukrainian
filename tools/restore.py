"""Restore the original game files from the backup made by apply.py.

    python tools\\restore.py
    python tools\\restore.py --bundle-dir DIR --backup-dir DIR
    python tools\\restore.py --assembly     (also restore Assembly-CSharp.dll)

The bundle backup lives in `_uk_backup\\`; the assembly backup is created next
to the DLL by the AssemblyPatcher (`Assembly-CSharp.dll.uk_backup`).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import lib_swc as swc


def restore_bundles(bundle_dir: Path, backup_dir: Path) -> int:
    if not backup_dir.is_dir():
        print(f"No backup folder at {backup_dir}", file=sys.stderr)
        return 2
    backups = sorted(backup_dir.glob("*.bundle"))
    if not backups:
        print("No bundle backups found.", file=sys.stderr)
        return 2
    print(f"Restoring {len(backups)} bundles to {bundle_dir}")
    for index, backup in enumerate(backups):
        if index % 10 == 0:
            print(f"  restoring {index + 1}/{len(backups)} ...", flush=True)
        swc.copy_with_dirs(backup, bundle_dir / backup.name)
    print("Bundles restored.")
    return 0


def restore_assembly(project: Path) -> int:
    print("Restoring Assembly-CSharp.dll ...")
    result = subprocess.run(
        ["dotnet", "run", "--project", str(project), "-c", "Release",
         "--", "--restore"],
        cwd=str(swc.GAME_ROOT),
    )
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle-dir", type=Path, default=swc.BUNDLE_DIR)
    parser.add_argument("--backup-dir", type=Path, default=swc.DEFAULT_BACKUP_DIR)
    parser.add_argument("--assembly", action="store_true",
                        help="also restore Assembly-CSharp.dll")
    parser.add_argument("--project", type=Path,
                        default=swc.TOOLS_DIR / "AssemblyPatcher")
    args = parser.parse_args(argv)

    result = restore_bundles(args.bundle_dir, args.backup_dir)
    if result != 0:
        return result
    if args.assembly:
        result = restore_assembly(args.project)
        if result != 0:
            print("Assembly restore failed.", file=sys.stderr)
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
