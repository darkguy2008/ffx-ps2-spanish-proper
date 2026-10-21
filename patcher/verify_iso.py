import struct

from tqdm import tqdm

from disc_table import LBA_MASK, PAD_UNIT, SECTOR, file_spans, read_entries
from ffx_codec import END_TOKEN, STORED, decode
from game_program import PROGRAM_PATCHES, game_program, patch_offset
from rebuild_iso import ANCHOR_SECTOR, PVD_SECTOR, PVD_VOLUME_SIZE, SIZE_TABLE_ENTRY, SIZE_TABLE_INDEX
from udf_tag import seal


def read_span(handle, span):
    handle.seek(span[0] * SECTOR)
    return handle.read(span[1])


def main(original_path, rebuilt_path):
    old_spans = file_spans(read_entries(original_path))
    new_entries = read_entries(rebuilt_path)
    new_spans = file_spans(new_entries)
    problems = []
    changed = 0
    with open(original_path, 'rb') as old, open(rebuilt_path, 'rb') as new:
        new.seek(0, 2)
        total = new.tell() // SECTOR
        size_table = read_span(new, new_spans[SIZE_TABLE_INDEX])
        for index, (old_span, new_span) in tqdm(enumerate(zip(old_spans, new_spans)), total=len(old_spans), desc='Comparing files', unit='file', leave=False):
            if (old_span is None) != (new_span is None):
                problems.append(f'{index}: presence changed')
                continue
            if old_span is None:
                continue
            old_data, new_data = read_span(old, old_span), read_span(new, new_span)
            if index != SIZE_TABLE_INDEX and old_data != new_data:
                changed += 1
            plain = new_data
            if new_span[2]:
                plain, end = decode(new_data)
                if new_data[0] != STORED and new_data[end:end + 1] != bytes([END_TOKEN]):
                    problems.append(f'{index}: no end token after stream')
            recorded = int.from_bytes(size_table[index * SIZE_TABLE_ENTRY:(index + 1) * SIZE_TABLE_ENTRY], 'little')
            if index != SIZE_TABLE_INDEX and index * SIZE_TABLE_ENTRY < len(size_table) and recorded != -(-len(plain) // PAD_UNIT) and old_data != new_data:
                problems.append(f'{index}: size table {recorded * PAD_UNIT} vs {len(plain)}')
        new.seek(PVD_SECTOR * SECTOR + PVD_VOLUME_SIZE)
        if struct.unpack('<I', new.read(4))[0] != total:
            problems.append('PVD volume size wrong')
        for sector in (ANCHOR_SECTOR, total - 1):
            new.seek(sector * SECTOR)
            descriptor = new.read(SECTOR)
            if seal(descriptor, sector) != descriptor or struct.unpack_from('<H', descriptor)[0] != 2:
                problems.append(f'UDF anchor at {sector} invalid')
    program = game_program(rebuilt_path)[1]
    for before, _, after, new in PROGRAM_PATCHES:
        try:
            patch_offset(program, before, new, after)
        except ValueError as error:
            problems.append(str(error))
    print('files changed', changed, 'sectors', total, 'end marker', max(raw & LBA_MASK for raw in new_entries if raw))
    if problems:
        raise SystemExit(f'{rebuilt_path} failed verification: {problems}')
