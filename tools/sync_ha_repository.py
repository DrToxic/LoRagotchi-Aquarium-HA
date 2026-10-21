#!/usr/bin/env python3
"""Generate/check Supervisor's build directory from the canonical root source."""
import argparse
from pathlib import Path
import tempfile
import uuid
import zipfile

from package_ha import ROOT, package


def files(folder):
    if not folder.exists():
        return {}
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in folder.rglob("*") if path.is_file()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on missing, stale or extra files")
    args = parser.parse_args()
    destination = ROOT / "loragotchi_aquarium"
    if destination.is_symlink():
        raise SystemExit("Refusing a symlinked generated directory")
    # Stage on the same filesystem for atomic directory renames.
    with tempfile.TemporaryDirectory(prefix=".ha-package-", dir=ROOT) as temporary:
        staging = Path(temporary)
        archive = staging / "addon.zip"
        package(archive)
        with zipfile.ZipFile(archive) as source:
            source.extractall(staging)
        generated = staging / "loragotchi_aquarium"
        expected, actual = files(generated), files(destination)
        different = sorted(name for name in expected.keys() | actual.keys()
                           if expected.get(name) != actual.get(name))
        if args.check:
            if different:
                raise SystemExit("Generated add-on differs; run tools/sync_ha_repository.py:\n"
                                 + "\n".join(different))
        elif different:
            backup = None
            if destination.exists():
                backup = ROOT / ".local" / ("ha-package-backup-" + uuid.uuid4().hex)
                backup.parent.mkdir(exist_ok=True)
                destination.rename(backup)
            try:
                generated.rename(destination)
            except BaseException:
                if backup is not None:
                    backup.rename(destination)
                raise
            if backup is not None:
                print(f"Previous generated context retained at {backup.relative_to(ROOT)}")
        print(f"Add-on context: {len(expected)} files {'verified' if args.check else 'synchronized'}")


if __name__ == "__main__":
    main()
