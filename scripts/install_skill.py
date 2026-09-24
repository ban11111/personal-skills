#!/usr/bin/env python3
"""Install one local skill without overwriting existing user files."""
import argparse
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def install(name, target, copy=False, root=ROOT):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
        raise ValueError('invalid skill id')
    source = root / 'skills' / name
    if not (source / 'SKILL.md').is_file() or source.is_symlink():
        raise ValueError('skill must be a real directory with SKILL.md')
    target = Path(target).expanduser().resolve()
    destination = target / name
    if destination.is_symlink() and destination.resolve() == source.resolve() and not copy:
        return destination, 'already linked'
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f'refusing to overwrite {destination}')
    if target == source.resolve() or source.resolve() in target.parents:
        raise ValueError('installation target cannot be inside the source skill')
    target.mkdir(parents=True, exist_ok=True)
    if copy:
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    else:
        destination.symlink_to(source.resolve(), target_is_directory=True)
    return destination, 'copied' if copy else 'linked'


def main():
    default = Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex') / 'skills'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('skill')
    parser.add_argument('--target', type=Path, default=default)
    parser.add_argument('--copy', action='store_true')
    args = parser.parse_args()
    try:
        path, status = install(args.skill, args.target, args.copy)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f'{status}: {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
