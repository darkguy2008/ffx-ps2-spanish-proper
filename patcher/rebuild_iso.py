import struct

from tqdm import tqdm

from disc_table import DUMMY, ID_SECTOR, LBA_MASK, PAD_UNIT, SECTOR, file_spans, read_entries
from udf_tag import seal

SIZE_TABLE_INDEX = 15
SIZE_TABLE_ENTRY = 3
PVD_SECTOR = 16
PVD_VOLUME_SIZE = 80
ANCHOR_SECTOR = 256
ANCHOR_MAIN_VDS = 16
ANCHOR_RESERVE_VDS = 24
PARTITION_TAG = 5
PARTITION_LENGTH = 192
PAD_SHIFT = 24
COPY_CHUNK = 1 << 26


def sectors_for(size):
    return -(-size // SECTOR)


def pad_byte(size):
    return (sectors_for(size) * SECTOR - size) // PAD_UNIT


def copy_range(source, target, start_sector, sector_count):
    source.seek(start_sector * SECTOR)
    remaining = sector_count * SECTOR
    while remaining:
        block = source.read(min(COPY_CHUNK, remaining))
        target.write(block)
        remaining -= len(block)


def file_starts(entries):
    starts = {}
    for index, raw in enumerate(entries):
        if raw and not raw & DUMMY:
            starts.setdefault(raw & LBA_MASK, index)
    return starts


def lay_out(entries, starts, replacements, end_lba):
    ordered = sorted(starts)
    first_changed = min(entries[index] & LBA_MASK for index in replacements)
    new_lba = {lba: lba for lba in ordered if lba < first_changed}
    plan = []
    cursor = first_changed
    for position, lba in enumerate(ordered):
        if lba < first_changed:
            continue
        following = ordered[position + 1] if position + 1 < len(ordered) else end_lba
        new_lba[lba] = cursor
        owner = starts[lba]
        if owner in replacements:
            plan.append(('new', owner))
            cursor += sectors_for(len(replacements[owner]))
        else:
            plan.append(('copy', lba, following - lba))
            cursor += following - lba
    new_lba[end_lba] = cursor
    return first_changed, new_lba, plan, cursor


def rewrite_entries(entries, new_lba, replacements):
    rewritten = []
    for index, raw in enumerate(entries):
        if not raw:
            rewritten.append(raw)
            continue
        flags_and_pad = raw & ~LBA_MASK
        if index in replacements:
            flags_and_pad = (raw & ~LBA_MASK & ((1 << PAD_SHIFT) - 1)) | pad_byte(len(replacements[index])) << PAD_SHIFT
        rewritten.append(flags_and_pad | new_lba[raw & LBA_MASK])
    return rewritten


def patch_size_table(size_table, unpacked_sizes):
    table = bytearray(size_table)
    for index, size in unpacked_sizes.items():
        offset = index * SIZE_TABLE_ENTRY
        table[offset:offset + SIZE_TABLE_ENTRY] = (-(-size // PAD_UNIT)).to_bytes(SIZE_TABLE_ENTRY, 'little')
    return bytes(table)


def read_sector(handle, sector):
    handle.seek(sector * SECTOR)
    return handle.read(SECTOR)


def write_sector(handle, sector, data):
    handle.seek(sector * SECTOR)
    handle.write(data)


def update_udf(target, old_total, new_total):
    anchor = read_sector(target, ANCHOR_SECTOR)
    for extent_offset in (ANCHOR_MAIN_VDS, ANCHOR_RESERVE_VDS):
        length, location = struct.unpack_from('<II', anchor, extent_offset)
        for sector in range(location, location + length // SECTOR):
            descriptor = bytearray(read_sector(target, sector))
            if struct.unpack_from('<H', descriptor)[0] == PARTITION_TAG:
                old_length = struct.unpack_from('<I', descriptor, PARTITION_LENGTH)[0]
                struct.pack_into('<I', descriptor, PARTITION_LENGTH, old_length + new_total - old_total)
                write_sector(target, sector, seal(descriptor, sector))
    write_sector(target, new_total - 1, seal(read_sector(target, new_total - 1), new_total - 1))


def update_pvd(target, new_total):
    target.seek(PVD_SECTOR * SECTOR + PVD_VOLUME_SIZE)
    target.write(struct.pack('<I', new_total) + struct.pack('>I', new_total))


def rebuild(source_path, target_path, replacements, unpacked_sizes):
    entries = read_entries(source_path)
    with open(source_path, 'rb') as source:
        layout = struct.unpack('<8I', read_sector(source, ID_SECTOR)[:32])
        table_sector = layout[4]
        source.seek(0, 2)
        old_total = source.tell() // SECTOR
        end_lba = max(raw & LBA_MASK for raw in entries if raw)
        starts = file_starts(entries)
        first_changed, new_lba, plan, data_end = lay_out(entries, starts, replacements, end_lba)
        new_total = data_end + old_total - end_lba
        with open(target_path, 'wb') as output, tqdm.wrapattr(output, 'write', total=new_total * SECTOR, desc='Writing ISO', leave=False) as target:
            copy_range(source, target, 0, first_changed)
            for step in plan:
                if step[0] == 'copy':
                    copy_range(source, target, step[1], step[2])
                else:
                    data = replacements[step[1]]
                    target.write(data + b'\0' * (sectors_for(len(data)) * SECTOR - len(data)))
            copy_range(source, target, end_lba, old_total - end_lba)
        size_table_lba, size_table_size, _ = file_spans(entries)[SIZE_TABLE_INDEX]
        source.seek(size_table_lba * SECTOR)
        size_table = source.read(size_table_size)
    with open(target_path, 'r+b') as target:
        target.seek(table_sector * SECTOR)
        target.write(struct.pack(f'<{len(entries)}I', *rewrite_entries(entries, new_lba, replacements)))
        target.seek(new_lba[size_table_lba] * SECTOR)
        target.write(patch_size_table(size_table, unpacked_sizes))
        update_pvd(target, new_total)
        update_udf(target, old_total, new_total)
    return old_total, new_total
