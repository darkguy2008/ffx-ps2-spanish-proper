import struct

HEADER_WORD = 4
OFFSET_MASK = 0xffff
PREFIX = 0x04
TIME = 0x09
CONTROLLER = 0x0b
CHOICE = 0x10
NEWLINE = 0x03
DOUBLE_BYTE_CHARACTER = 0x06
FIRST_DOUBLE_BYTE_SECTION = 0x26
FIRST_CHARACTER = 0x30
SINGLE_BYTE_CODES = {0x01, 0x02, NEWLINE, PREFIX, 0x05, 0x0c, 0x0f, 0x11}


def headers(text):
    count = (struct.unpack_from('<I', text)[0] & OFFSET_MASK) // HEADER_WORD
    return struct.unpack_from(f'<{count}I', text)


def tokens(text, start):
    position, prefixed = start, False
    while position < len(text) and text[position]:
        code = text[position]
        paired = code < FIRST_CHARACTER and (code == DOUBLE_BYTE_CHARACTER or code >= FIRST_DOUBLE_BYTE_SECTION
                                            or (not prefixed and code not in SINGLE_BYTE_CODES))
        width = 2 if paired else 1
        yield position, text[position:position + width], prefixed
        prefixed = code == PREFIX and not prefixed
        position += width


def code_tokens(text, start, code):
    return [(position, token) for position, token, prefixed in tokens(text, start) if token[0] == code and not prefixed]


def params(lines, code):
    return {token[1:] for line in lines for _, token in code_tokens(line, 0, code)}


def with_disc_codes(line, english, buttons, times):
    english_buttons = [token for _, token in code_tokens(english, 0, CONTROLLER)]
    kept, ordinal = b'', 0
    for _, token, prefixed in tokens(line, 0):
        if not prefixed and token[0] == CONTROLLER:
            kept += token if token[1:] in buttons else english_buttons[ordinal]
            ordinal += 1
        elif prefixed or token[0] != TIME or token[1:] in times:
            kept += token
    return kept


def lines_of(text):
    return [string_from(text, header & OFFSET_MASK) for header in headers(text)] if len(text) >= HEADER_WORD else []


def is_character(token):
    return len(token) == 1 and token[0] >= FIRST_CHARACTER


def decoded(line, charset):
    readable = ''
    for _, token, _ in tokens(line, 0):
        if token == bytes([NEWLINE]):
            readable += '\n'
        elif is_character(token):
            readable += charset[token[0] - FIRST_CHARACTER]
        else:
            readable += '{' + token.hex() + '}'
    return readable


def encoded(readable, charset):
    data = bytearray()
    rest = readable
    while rest:
        if rest[0] == '{':
            code, _, rest = rest[1:].partition('}')
            data += bytes.fromhex(code)
        else:
            data.append(NEWLINE if rest[0] == '\n' else FIRST_CHARACTER + charset.index(rest[0]))
            rest = rest[1:]
    return bytes(data)


def with_offsets(table, new_offset, body):
    rebuilt = [header & ~OFFSET_MASK | new_offset(header & OFFSET_MASK) for header in table]
    return struct.pack(f'<{len(rebuilt)}I', *rebuilt) + body


def string_from(text, start):
    return text[start:text.index(0, start)]


def first_numbers(text):
    first_header = {}
    for number, header in enumerate(headers(text)):
        first_header.setdefault(header & OFFSET_MASK, number)
    return first_header


def with_strings(text, overrides):
    table = headers(text)
    first_header = first_numbers(text)
    body, moved = b'', {}
    for start in sorted(first_header):
        original = string_from(text, start)
        string = overrides.get(first_header[start], original)
        if len(code_tokens(string, 0, CHOICE)) != len(code_tokens(original, 0, CHOICE)):
            raise ValueError(f'string {first_header[start]} changes its choices')
        moved[start] = len(table) * HEADER_WORD + len(body)
        body += string + b'\0'
    return with_offsets(table, moved.get, body)
