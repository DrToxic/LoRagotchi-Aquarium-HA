#!/usr/bin/env python3
"""Generate an HA local-app build context from this source; no maintained fork."""
import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def package(output):
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='aquarium-ha-package-') as temporary:
        folder=Path(temporary)/'loragotchi_aquarium';folder.mkdir()
        for name in ('Dockerfile','pyproject.toml','README.md','LICENSE','.dockerignore'):
            shutil.copy2(ROOT/name,folder/name)
        for name in ('tank','container'):
            shutil.copytree(ROOT/name,folder/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copy2(ROOT/'homeassistant/config.yaml.in',folder/'config.yaml')
        shutil.copytree(ROOT/'homeassistant/translations',folder/'translations')
        shutil.copy2(ROOT/'docs/HOME_ASSISTANT.md',folder/'DOCS.md')
        (folder/'docs').mkdir()
        shutil.copy2(ROOT/'docs/FISH-LIFESPAN.md',folder/'docs/FISH-LIFESPAN.md')
        shutil.copy2(ROOT/'docs/FISH-LIFESPAN.md',folder/'FISH-LIFESPAN.md')
        shutil.copy2(ROOT/'docs/THEMES.md',folder/'docs/THEMES.md')
        shutil.copy2(ROOT/'docs/THEMES.md',folder/'THEMES.md')
        shutil.copy2(ROOT/'docs/SCENERY.md',folder/'docs/SCENERY.md')
        for name in ('LIVING-AQUARIUM.md','DX-EGG-CONTRACT.md'):
            shutil.copy2(ROOT/'docs'/name,folder/'docs'/name)
        shutil.copy2(ROOT/'homeassistant/CHANGELOG.md',folder/'CHANGELOG.md')
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(temporary))
    print(output)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    package(parser.parse_args().output)
