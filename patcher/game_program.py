import io

import pycdlib

from disc_table import SECTOR

GAME_PROGRAM = '/SLPS_250.88;1'
NEW_GAME_LANGUAGE_RESET = bytes.fromhex('0001422a f9ff4014 00000000 9ef4060c')
JAPANESE_DEFAULT = bytes.fromhex('2d200000')
ENGLISH_DEFAULT = bytes.fromhex('01000424')
REGION_FOR_BUTTON_SWAP = bytes.fromhex('18650b0c')
STORE_BUTTON_SWAP = bytes.fromhex('5800103c e80902a2')
ALWAYS_SWAP_BUTTONS = bytes.fromhex('01000224')
PROGRAM_PATCHES = ((NEW_GAME_LANGUAGE_RESET, JAPANESE_DEFAULT, b'', ENGLISH_DEFAULT),
                   (b'', REGION_FOR_BUTTON_SWAP, STORE_BUTTON_SWAP, ALWAYS_SWAP_BUTTONS))


def game_program(iso_path):
    iso = pycdlib.PyCdlib()
    iso.open(iso_path)
    program = io.BytesIO()
    iso.get_file_from_iso_fp(program, iso_path=GAME_PROGRAM)
    start = iso.get_record(iso_path=GAME_PROGRAM).extent_location() * SECTOR
    iso.close()
    return start, program.getvalue()


def patch_offset(program, before, value, after):
    pattern = before + value + after
    found = program.count(pattern)
    if found != 1:
        raise ValueError(f'game program pattern {pattern.hex()} found {found} times')
    return program.index(pattern) + len(before)


def patch_program(iso_path):
    start, program = game_program(iso_path)
    with open(iso_path, 'r+b') as iso:
        for before, old, after, new in PROGRAM_PATCHES:
            iso.seek(start + patch_offset(program, before, old, after))
            iso.write(new)
