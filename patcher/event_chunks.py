import struct

CHUNK_TABLE = 4
EVENT_CHUNK_COUNT = 6
LOCAL_TEXT = 1
ENGLISH_TEXT = 4
BATTLE_CHUNK_COUNT = 8
BATTLE_ENGLISH_TEXT = 6
CHUNK_ALIGN = 0x10


def chunk_offsets(plain, count=EVENT_CHUNK_COUNT):
    return list(struct.unpack_from(f'<{count}I', plain, CHUNK_TABLE))


def chunk(plain, number, count=EVENT_CHUNK_COUNT):
    offsets = chunk_offsets(plain, count)
    start = offsets[number]
    later = [offset for offset in offsets if offset > start]
    return plain[start:min(later + [len(plain)])]


def replace_last_chunk(plain, number, payload, count=EVENT_CHUNK_COUNT):
    offsets = chunk_offsets(plain, count)
    start = offsets[number] or len(plain)
    if any(offset > start for offset in offsets[:number] + offsets[number + 1:count - 1]):
        raise ValueError('chunk is not last')
    padded = payload + b'\0' * (-len(payload) % CHUNK_ALIGN)
    rebuilt = bytearray(plain[:start] + padded)
    offsets[number], offsets[count - 1] = start, len(rebuilt)
    struct.pack_into(f'<{count}I', rebuilt, CHUNK_TABLE, *offsets)
    return bytes(rebuilt)
