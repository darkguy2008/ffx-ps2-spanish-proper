import functools
import struct

SECTOR = 2048
ID_SECTOR = 279
LBA_MASK = (1 << 22) - 1
FLAG_22 = 1 << 22
DUMMY = 1 << 23
PAD_UNIT = 8


def read_entries(iso_path):
    with open(iso_path, "rb") as iso:
        iso.seek(ID_SECTOR * SECTOR)
        layout = struct.unpack("<8I", iso.read(32))
        table_sector, table_bytes = layout[4], layout[5]
        iso.seek(table_sector * SECTOR)
        return list(struct.unpack(f"<{table_bytes // 4}I", iso.read(table_bytes)))


@functools.cache
def iso_spans(iso_path):
    return file_spans(read_entries(iso_path))


def file_spans(entries):
    spans = []
    for index, raw in enumerate(entries):
        if raw == 0 or raw & DUMMY:
            spans.append(None)
            continue
        lba = raw & LBA_MASK
        next_lba = next((other & LBA_MASK for other in entries[index + 1:] if other & LBA_MASK > lba), None)
        if next_lba is None:
            spans.append(None)
            continue
        size = (next_lba - lba) * SECTOR - (raw >> 24) * PAD_UNIT
        spans.append((lba, size, bool(raw & FLAG_22)))
    return spans
