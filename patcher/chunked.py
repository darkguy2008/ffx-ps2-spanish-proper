import struct

ALIGN = 0x10


def split(data, count):
    offsets = struct.unpack_from(f'<{count}I', data)
    chunks = []
    for offset in offsets:
        later = [other for other in offsets if other > offset]
        chunks.append(data[offset:min(later + [len(data)])] if offset else None)
    return chunks


def join(chunks):
    header_size = len(chunks) * 4
    body = bytearray(header_size + (-header_size % ALIGN))
    offsets = []
    for chunk in chunks:
        if chunk is None:
            offsets.append(0)
            continue
        offsets.append(len(body))
        body += chunk + b'\0' * (-len(chunk) % ALIGN)
    struct.pack_into(f'<{len(chunks)}I', body, 0, *offsets)
    return bytes(body)
