#!/usr/bin/env python3
"""Clean outputs: remove duplicate profiles (keep newest per username), remove
profiles without binding_protocol.md, remove temporary 'profiles' folder.
Then clean repo-wide temp files (__pycache__, .pytest_cache, logs, etc.)."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def parse_dir_name(name: str) -> tuple[str, str] | None:
    """Return (timestamp, username) for names like 20260210_065327_0xMontBlanc."""
    parts = name.split("_", 2)
    if len(parts) >= 3:
        return (f"{parts[0]}_{parts[1]}", parts[2])
    if len(parts) == 2:
        return (parts[0], parts[1])
    return None


def has_binding_protocol(path: Path) -> bool:
    """Require binding_protocol.md for a valid profile."""
    return (path / "binding_protocol.md").exists()


def clean_outputs(base: Path, dry_run: bool) -> None:
    """Remove profiles folder, no-binding dirs, and duplicate run dirs (keep newest per user)."""
    # 1) Remove temporary "profiles" folder
    profiles_dir = base / "profiles"
    if profiles_dir.is_dir():
        if dry_run:
            print(f"[dry-run] Would remove: {profiles_dir}")
        else:
            shutil.rmtree(profiles_dir)
            print(f"Removed: {profiles_dir}")

    # 2) Remove run dirs without binding_protocol.md
    candidates: list[tuple[Path, str, str]] = []
    for item in base.iterdir():
        if not item.is_dir():
            continue
        name = item.name
        if name == "profiles":
            continue
        parsed = parse_dir_name(name)
        if not parsed:
            continue
        ts, username = parsed
        if not has_binding_protocol(item):
            if dry_run:
                print(f"[dry-run] Would remove (no binding_protocol.md): {item.name}")
            else:
                shutil.rmtree(item)
                print(f"Removed (no binding_protocol.md): {item.name}")
            continue
        candidates.append((item, ts, username))

    # 3) Deduplicate by username (case-insensitive), keep newest
    by_user: dict[str, list[tuple[Path, str]]] = {}
    for path, ts, username in candidates:
        key = username.lower()
        by_user.setdefault(key, []).append((path, ts))
    for key, list_of_paths in by_user.items():
        list_of_paths.sort(key=lambda x: x[1], reverse=True)
        for path in [p for p, _ in list_of_paths[1:]]:
            if dry_run:
                print(f"[dry-run] Would remove (duplicate): {path.name}")
            else:
                shutil.rmtree(path)
                print(f"Removed (duplicate): {path.name}")


def clean_repo_temp(repo_root: Path, dry_run: bool) -> None:
    """Remove repo-wide temporary files and dirs."""
    skip_dirs = {".git", "venv", ".venv", "env", "target", "node_modules"}
    to_remove_dirs: list[Path] = []
    to_remove_files: list[Path] = []
    for dirpath in repo_root.rglob("*"):
        if not dirpath.is_dir():
            if dirpath.suffix == ".pyc":
                to_remove_files.append(dirpath)
            continue
        if dirpath.name in skip_dirs:
            continue
        if dirpath.name in ("__pycache__", ".pytest_cache", "logs", ".cache"):
            to_remove_dirs.append(dirpath)
    # Remove dirs (children before parents by reverse sort on path parts)
    to_remove_dirs.sort(key=lambda p: (len(p.parts), str(p)), reverse=True)
    for dirpath in to_remove_dirs:
        if dry_run:
            print(f"[dry-run] Would remove: {dirpath}")
        else:
            shutil.rmtree(dirpath, ignore_errors=True)
            print(f"Removed: {dirpath}")
    for f in to_remove_files:
        if dry_run:
            print(f"[dry-run] Would remove: {f}")
        else:
            try:
                f.unlink()
                print(f"Removed: {f}")
            except OSError:
                pass
    # Temp files in outputs
    for name in ("CLEANUP.bat", "latest.txt", "c2.sqlite", "holespawn.sqlite"):
        f = repo_root / "outputs" / name
        if f.exists():
            if dry_run:
                print(f"[dry-run] Would remove: {f}")
            else:
                try:
                    if f.is_dir():
                        shutil.rmtree(f)
                    else:
                        f.unlink()
                    print(f"Removed: {f}")
                except OSError:
                    pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outputs_dir", nargs="?", type=Path, default=Path("outputs"), help="Outputs directory")
    ap.add_argument("--dry-run", action="store_true", help="Only print what would be removed")
    ap.add_argument("--outputs-only", action="store_true", help="Only clean outputs, skip repo-wide temp")
    args = ap.parse_args()
    base = args.outputs_dir.resolve()
    repo_root = base.parent if base.name == "outputs" else base

    if base.is_dir():
        clean_outputs(base, args.dry_run)
    else:
        print(f"Outputs not a directory: {base}")

    if not args.outputs_only and repo_root.exists():
        clean_repo_temp(repo_root, args.dry_run)

    if args.dry_run:
        print("Dry run done. Run without --dry-run to apply.")
    else:
        print("Cleanup done.")


if __name__ == "__main__":
    main()
