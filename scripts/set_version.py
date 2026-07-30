#!/usr/bin/env python3
import argparse
import os
import pathlib
import re
import tempfile


VERSION_PATTERN = re.compile(r'^\d+\.\d+(?:\.\d+)?$')
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION_FILE = PROJECT_ROOT / 'VERSION'


def validate_version(value):
    version = value.strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError('Version must use major.minor or major.minor.patch')
    return version


def set_version(value, version_file=VERSION_FILE):
    version = validate_version(value)
    destination = pathlib.Path(version_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix='.VERSION.',
        dir=str(destination.parent),
        text=True,
    )
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as temporary_file:
            temporary_file.write(version + '\n')
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return version


def main():
    parser = argparse.ArgumentParser(description='Update the OPEN-VELOJOL version.')
    parser.add_argument('version', help='Version in major.minor or major.minor.patch format')
    args = parser.parse_args()

    try:
        version = set_version(args.version)
    except ValueError as exc:
        parser.error(str(exc))
    print(f'VERSION updated to {version}')


if __name__ == '__main__':
    main()
