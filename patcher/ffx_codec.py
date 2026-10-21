HEADER = 5
RUN_TOKEN = 0x7e
LONG_RUN_TOKEN = 0x7f
MATCH_FLAG = 0x80
END_TOKEN = 0
RUN_BIAS = 4
MATCH_BIAS = 3
STORED = 0
DISTANCE_BITS = {1: 11, 2: 12}


def decode(packed, limit=None):
    size = int.from_bytes(packed[1:4], 'little')
    size = min(size, limit or size)
    if packed[0] == STORED:
        return packed[HEADER:HEADER + size], HEADER + size
    distance_bits = DISTANCE_BITS[packed[0]]
    high_distance_bits = distance_bits - 8
    length_mask = (1 << (7 - high_distance_bits)) - 1
    out = bytearray()
    pos = HEADER
    while len(out) < size:
        token = packed[pos]
        if token < RUN_TOKEN:
            out += packed[pos + 1:pos + 1 + token]
            pos += 1 + token
        elif token == RUN_TOKEN:
            out += bytes([packed[pos + 2]]) * (packed[pos + 1] + RUN_BIAS)
            pos += 3
        elif token == LONG_RUN_TOKEN:
            out += bytes([packed[pos + 3]]) * int.from_bytes(packed[pos + 1:pos + 3], 'little')
            pos += 4
        else:
            distance = ((token & ((1 << high_distance_bits) - 1)) << 8 | packed[pos + 1]) + 1
            for _ in range(((token >> high_distance_bits) & length_mask) + MATCH_BIAS):
                out.append(out[-distance] if distance <= len(out) else 0)
            pos += 2
    return bytes(out[:size]), pos


def decompress(packed, limit=None):
    return decode(packed, limit)[0]


MAX_LITERAL = RUN_TOKEN - 1
MAX_SHORT_RUN = 0xff + RUN_BIAS
MAX_LONG_RUN = 0xffff
MIN_RUN = RUN_BIAS
HASH_BYTES = MATCH_BIAS
MAX_CANDIDATES = 64


def compress(plain, kind):
    high_distance_bits = DISTANCE_BITS[kind] - 8
    max_distance = 1 << DISTANCE_BITS[kind]
    max_length = (1 << (7 - high_distance_bits)) - 1 + MATCH_BIAS
    out = bytearray([kind]) + len(plain).to_bytes(3, 'little') + b'\0'
    literals = bytearray()
    chains = {}

    def flush_literals():
        for start in range(0, len(literals), MAX_LITERAL):
            chunk = literals[start:start + MAX_LITERAL]
            out.append(len(chunk))
            out.extend(chunk)
        literals.clear()

    def remember(position):
        key = plain[position:position + HASH_BYTES]
        chains.setdefault(key, []).append(position)

    pos = 0
    while pos < len(plain):
        run = 1
        while pos + run < len(plain) and run < MAX_LONG_RUN and plain[pos + run] == plain[pos]:
            run += 1
        best_length, best_distance = 0, 0
        for candidate in reversed(chains.get(plain[pos:pos + HASH_BYTES], [])[-MAX_CANDIDATES:]):
            distance = pos - candidate
            if distance > max_distance:
                break
            length = 0
            while length < max_length and pos + length < len(plain) and plain[candidate + length] == plain[pos + length]:
                length += 1
            if length > best_length:
                best_length, best_distance = length, distance
        if run >= MIN_RUN and run > best_length:
            flush_literals()
            if run <= MAX_SHORT_RUN:
                out += bytes([RUN_TOKEN, run - RUN_BIAS, plain[pos]])
            else:
                out += bytes([LONG_RUN_TOKEN]) + run.to_bytes(2, 'little') + bytes([plain[pos]])
            step = run
        elif best_length >= MATCH_BIAS:
            flush_literals()
            encoded_distance = best_distance - 1
            out += bytes([MATCH_FLAG | (best_length - MATCH_BIAS) << high_distance_bits | encoded_distance >> 8, encoded_distance & 0xff])
            step = best_length
        else:
            literals.append(plain[pos])
            step = 1
        for position in range(pos, pos + step):
            remember(position)
        pos += step
    flush_literals()
    out.append(END_TOKEN)
    return bytes(out)
