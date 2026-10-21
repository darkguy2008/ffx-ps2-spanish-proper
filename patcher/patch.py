import argparse
import hashlib
import json
import os

from tqdm import tqdm

import build_patch
import catalog
import verify_iso
from progress import run_reporting, run_steps

PATCHER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(PATCHER)
WORK = os.path.join(REPO, 'build')
REMASTER_ROOT = os.path.join(WORK, 'vbf')
INTERNATIONAL_CATALOG = os.path.join(WORK, 'catalog_international.json')
SPAIN_CATALOG = os.path.join(WORK, 'catalog_spain.json')
VBF_TOOL = os.path.join(REPO, 'vendor/vbfextract/bin/Release/VBFTool.exe')
EXTRACT_VBF = os.path.join(WORK, 'extract_vbf.exe')
CATALOG_FOLDERS = ('jppc', 'inpc', 'uspc')
INTERNATIONAL_SHA1 = '6c97681f621716024f9a16f84c0835c06dd4bfd7'
SPAIN_SHA1 = '6f69e3a99204fbcf236829e9ceafade33e5bf6e4'
HASH_BLOCK = 1 << 24


def require_dump(path, expected, title):
    digest = hashlib.sha1()
    with open(path, 'rb') as disc, tqdm.wrapattr(disc, 'read', total=os.path.getsize(path), desc='SHA-1') as reader:
        while block := reader.read(HASH_BLOCK):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise SystemExit(f'{path} is not a Redump dump of {title} (SHA-1 {digest.hexdigest()}, expected {expected})')


def extract_remaster(vbf_path):
    run_reporting(['mono', EXTRACT_VBF, VBF_TOOL, vbf_path, REMASTER_ROOT], 'Extracting')


def write_catalog(iso_path, path):
    json.dump(catalog.build(iso_path, os.path.join(REMASTER_ROOT, build_patch.MASTER), CATALOG_FOLDERS), open(path, 'w'))


def main():
    parser = argparse.ArgumentParser(description='Build a Spanish Final Fantasy X International (PS2) ISO from your own game files.')
    parser.add_argument('international', help='Final Fantasy X International (Japan) (En,Ja) ISO, SLPS-25088')
    parser.add_argument('spain', help='Final Fantasy X (Spain) ISO, SCES-50494')
    parser.add_argument('vbf', help='FFX_Data.vbf from the Steam FINAL FANTASY X/X-2 HD Remaster')
    parser.add_argument('output', help='Spanish ISO to write')
    arguments = parser.parse_args()
    os.makedirs(WORK, exist_ok=True)
    steps = (
        ('Checking the International ISO', lambda: require_dump(arguments.international, INTERNATIONAL_SHA1, 'Final Fantasy X International (Japan) (En,Ja)')),
        ('Checking the Spain ISO', lambda: require_dump(arguments.spain, SPAIN_SHA1, 'Final Fantasy X (Spain)')),
        ("Extracting the remaster's PS2 files", lambda: extract_remaster(arguments.vbf)),
        ('Cataloging the International ISO', lambda: write_catalog(arguments.international, INTERNATIONAL_CATALOG)),
        ('Cataloging the Spain ISO', lambda: write_catalog(arguments.spain, SPAIN_CATALOG)),
        ('Building the Spanish ISO', lambda: build_patch.main(arguments.international, arguments.spain, REMASTER_ROOT, INTERNATIONAL_CATALOG, SPAIN_CATALOG, arguments.output)),
        ('Verifying the Spanish ISO', lambda: verify_iso.main(arguments.international, arguments.output)))
    run_steps(steps, 'Step')
    print(f'Done: {arguments.output}')


if __name__ == '__main__':
    main()
