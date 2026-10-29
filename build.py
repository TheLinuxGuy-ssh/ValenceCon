#!/usr/bin/env python

import argparse
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

import yaml


def indent(elem: ET.Element, level: int = 0) -> None:
    """
    Nicely formats output xml with newlines and spaces
    https://stackoverflow.com/a/33956544
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i


ADDON_ID = "plugin.video.valencecon"


def create_addon_xml(config: dict, source: str, py_version: str) -> None:
    """
    Create addon.xml from template file
    """
    # Load template file
    with open(f'{source}/.config/template.xml', 'r') as f:
        tree = ET.parse(f)
        root = tree.getroot()

    # Populate dependencies in template
    dependencies = config['dependencies'].get(py_version)
    for dep in dependencies:
        ET.SubElement(root.find('requires'), 'import', attrib=dep)

    # Populate version string
    addon_version = config.get('version')
    root.attrib['version'] = f'{addon_version}+{py_version}'

    # Populate Changelog
    date = datetime.today().strftime('%Y-%m-%d')
    changelog = config.get('changelog')
    for section in root.findall('extension'):
        news = section.findall('news')
        if news:
            news[0].text = f'v{addon_version} ({date}):\n{changelog}'

    # Format xml tree
    indent(root)

    # Write addon.xml
    tree.write(f'{source}/addon.xml', encoding='utf-8', xml_declaration=True)


def zip_files(py_version: str, source: str, target: str, dev: bool) -> None:
    """
    Create an installable ZIP archive using a format Kodi's macOS installer reads
    correctly. Kodi's bundled ZIP reader can misread uncompressed entries created
    by Python's ZIP_STORED default, shifting file contents into adjacent entries.
    """
    archive_name = f'{ADDON_ID}+{py_version}.zip'
    target_path = Path(target).absolute()
    target_path.mkdir(parents=True, exist_ok=True)
    archive_path = target_path / archive_name
    archive_path.unlink(missing_ok=True)

    zip_executable = shutil.which('zip')
    source_path = Path(source).absolute()

    with tempfile.TemporaryDirectory(prefix='valencecon-addon-') as temp_dir:
        staging_path = Path(temp_dir)
        addon_path = staging_path / ADDON_ID

        for root, dirs, files in os.walk(source_path):
            dirs[:] = [d for d in dirs if dev or folder_filter(os.path.join(root, d))]
            for filename in files:
                file_path = os.path.join(root, filename)
                if not file_filter(filename) or (not dev and not folder_filter(file_path)):
                    continue

                relative_path = Path(ADDON_ID) / Path(os.path.relpath(file_path, source_path))
                staged_file = staging_path / relative_path
                staged_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, staged_file)

        if zip_executable:
            # Info-ZIP output is compatible with Kodi's archive VFS on macOS.
            subprocess.run(
                [zip_executable, '-q', '-r', str(archive_path), ADDON_ID],
                cwd=staging_path,
                check=True,
            )
        else:
            # Keep the build usable on systems without the zip CLI.
            with zipfile.ZipFile(
                archive_path, 'w', compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for staged_file in addon_path.rglob('*'):
                    if staged_file.is_file():
                        archive.write(staged_file, staged_file.relative_to(staging_path))


def file_filter(file_name: str) -> bool:
    """
    True if file_name is meant to be included in the addon zip
    """
    # Exclude development/test files
    excluded_patterns = [
        'test_',
        '_test',
        '.test.',
        'test_results',
        '.pyc',
        '.pyo',
        '.pyd',
        '.zip',
        '.env',
        '.editorconfig',
        '.gitignore',
        'build.py',
        'CONTRIBUTING.md',
        'SECURITY.md',
        'tox.ini',
        'requirements-dev.txt',
        'release.yaml',
    ]

    for pattern in excluded_patterns:
        if pattern in file_name:
            return False

    # Exclude compiled Python files
    if file_name.endswith(('.pyc', '.pyo', '.pyd')):
        return False

    # Exclude previous zip files
    if file_name.startswith(ADDON_ID) and file_name.endswith('.zip'):
        return False

    return True


def folder_filter(folder_name: str) -> bool:
    """
    True if folder_name is meant to be included
    """
    filters = [
        '.ci',
        '.git',
        '.github',
        '.config',
        '.mypy_cache',
        '.pytest_cache',
        'tests',
        'tools',
        '__pycache__',
        'venv',
        '.idea',
        '.vscode',
    ]
    for f in filters:
        if f in folder_name.split(os.path.sep):
            return False

    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build flags:')
    parser.add_argument(
        '--version',
        type=str,
        choices=('py2', 'py3'),
        default='py3')

    parser.add_argument(
        '--source',
        type=Path,
        default=Path(__file__).absolute().parent)

    parser.add_argument(
        '--target',
        type=Path,
        default=Path(__file__).absolute().parent / 'dist')

    parser.add_argument('--dev', dest='dev', action='store_true')
    parser.set_defaults(dev=False)

    args = parser.parse_args()

    # Load config file
    config_path = os.path.join(args.source, 'release.yaml')
    with open(config_path, 'r') as fh:
        release_config = yaml.safe_load(fh)

    create_addon_xml(release_config, args.source, args.version)

    zip_files(args.version, args.source, args.target, args.dev)
