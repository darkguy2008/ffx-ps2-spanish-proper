import glob
import json
import os
import struct

from catalog import event_script_id, uncompressed_starting_with, unpacked_files
from chunked import join, split
from disc_table import PAD_UNIT, SECTOR, iso_spans
from event_chunks import BATTLE_CHUNK_COUNT, BATTLE_ENGLISH_TEXT, CHUNK_TABLE, ENGLISH_TEXT, EVENT_CHUNK_COUNT, LOCAL_TEXT, chunk, chunk_offsets, replace_last_chunk
from ffx_codec import compress, decompress
from ffx_text import CONTROLLER, FIRST_CHARACTER, HEADER_WORD, OFFSET_MASK, TIME, decoded, encoded, first_numbers, headers, lines_of, params, with_disc_codes, with_strings
from game_program import patch_program
from line_matching import glossary, translated_lines
from progress import run_reporting, run_steps
from rebuild_iso import rebuild

MASTER = 'ffx_ps2/ffx/master'
ENGLISH_REMASTER = 'new_uspc'
SPANISH_REMASTER = 'new_sppc'
SPANISH = f'{MASTER}/{SPANISH_REMASTER}'
MACRO_CHUNKS = 16
DISC_ONLY_MACRO_CHUNK = 9
ENGLISH_MACROS = 'uspc/menu/macrodic.dcp'
FONT_MAGIC = b'FTCX'
FONT_KIND = 8
BASE_FONT_KIND = 4
FONT_HEADER = 0x40
GLYPH_MAP_START = '0123456789'.translate(str.maketrans('0123456789', '０１２３４５６７８９')).encode('cp932')
LATIN_GLYPH_MAP_SIZE = 416
MENU_SET_SECOND_FILE = 'albheddic.bin'
MENU_SET_LENGTH = 20
MENU_HELP_TEXT = 'menumain.msb'
HELP_SET_SECOND_FILE = 'test_proj.sps2'
ENGLISH_HELP = 'jppc/help_inter/'
JAPANESE_HELP = 'jppc/help/'
HELP_TEXTURES = 'helpgra/'
JAPANESE_KERNEL = 'jppc/battle/kernel/'
ENGLISH_KERNEL = 'inpc/battle/kernel/'
KERNEL_SCRATCH = 'scratch/kernel'
MIN_BLOCK_PAIRS = 2
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
PARSER_JAR = os.path.join(SCRIPTS, '../vendor/FFXDataParser/target/FFXDataParser-1.2-SNAPSHOT.jar')
KERNEL_SPLICE = os.path.join(SCRIPTS, 'java/KernelSplice.java')
KERNEL_STRINGS = os.path.join(SCRIPTS, 'kernel_strings.csv')
MONSTER_SPLICE = os.path.join(SCRIPTS, 'java/MonsterTextSplice.java')
MONSTER_TABLES = 'monster*.bin'
MONSTER_SCRATCH = 'scratch/monster'
KERNEL_SPLICEABLE = ('command.bin', 'monmagic1.bin', 'monmagic2.bin', 'item.bin', 'important.bin', 'a_ability.bin', 'w_name.bin',
                     'sphere.bin', 'panel.bin', 'ply_save.bin', 'ply_rom.bin', 'arms_txt.bin', 'config_txt.bin', 'item_txt.bin',
                     'menu_txt.bin', 'mmain_txt.bin', 'status_txt.bin', 'summon_txt.bin')
STRING_TABLES = ('btl_txt.bin', 'btlend_txt.bin', 'build_txt.bin', 'name_txt.bin', 'save_txt.bin')
STRING_TABLE_FIELDS = '<IIHHHHI'
STRING_TABLE_HEADER = struct.calcsize(STRING_TABLE_FIELDS)
EVENT_STRINGS = os.path.join(SCRIPTS, 'event_strings.json')
PAL_BATTLE_LOCAL_TEXT = 4
CHARSET = 'jppc/ffx_encoding/ffxsjistbl_us.bin'
MENU_PALETTES = 'menu.clp'
MESSAGE_WINDOW = 'meswin.fmt'
ICONS = 'icon.fmt'
PAL_JAPANESE_MODE_FILES = (MENU_PALETTES, MESSAGE_WINDOW, ICONS)
PAL_MENU_FILES = (MENU_PALETTES, 'battle.fmt', MESSAGE_WINDOW, 'menumain.bin', ICONS, 'strtex.fmt', 'menu_script.bin', 'battle_script.bin')
MESSAGE_WINDOW_WIDTH = 256
GIL_LABEL_COLUMNS = range(120, 160)
GIL_LABEL_ROWS = range(11, 32)
MENU_PALETTES_WIDTH = 64
PALETTE_SIDE = 16
PALETTE_COLORS = PALETTE_SIDE * PALETTE_SIDE
COLOR_BYTES = 4
CSM1_SWAPPED_BITS = (0x08, 0x10)
ICONS_WIDTH = 256
ICON_PIXELS_PER_BYTE = 2
ICONS_ROW_BYTES = ICONS_WIDTH // ICON_PIXELS_PER_BYTE
CROSS_CIRCLE_COLUMNS = range(24, 72)
CROSS_CIRCLE_ROWS = range(56, 74)
TITLE_MAP = 'jppc/map/titl/titl00/bin/mapout.vpa'
MAP_TAIL_OFFSET_FIELD = 24
SCENE_QWORDS_FIELD = 180
SCENE_RECORDS_FIELD = 192
PICTURE_DEPENDENT_FIELDS = (MAP_TAIL_OFFSET_FIELD, SCENE_QWORDS_FIELD, SCENE_RECORDS_FIELD)
FIELD_BYTES = 4
TEXTURE_RECORD = struct.Struct('<4I')
QWORD = 16
TEXTURE_HEADER = TEXTURE_RECORD.size + QWORD
INDEXED = 1
RGBA = 2
BYTES_PER_PIXEL = {INDEXED: 1, RGBA: COLOR_BYTES}
PAL_TITLE_PICTURES = ('international', 'black', 'english', 'italian', 'french', 'german', 'spanish')
TITLE_WIDTH = 512
TITLE_TEXT_AREAS = ((range(44, 59), range(44, 384)), (range(280, 331), range(326, TITLE_WIDTH)))


def run_java_splice(source, arguments, vbf_root):
    run_reporting(['java', '-cp', PARSER_JAR, source, *arguments], f'Splicing {os.path.basename(source)}', vbf_root)


def read_file(iso_path, index):
    lba, size, _ = iso_spans(iso_path)[index]
    with open(iso_path, 'rb') as iso:
        iso.seek(lba * SECTOR)
        return iso.read(size)


def pad_to_unit(data):
    return data + b'\0' * (-len(data) % PAD_UNIT)


def packed_like(iso_path, index, plain):
    compressed = iso_spans(iso_path)[index][2]
    return pad_to_unit(compress(plain, read_file(iso_path, index)[0]) if compressed else plain)


def paired(english, spanish):
    return (english, spanish) if len(english) == len(spanish) else None


def remaster_paths(vbf_root, path):
    return tuple(f'{vbf_root}/{MASTER}/{language}/{path}' for language in (ENGLISH_REMASTER, SPANISH_REMASTER))


def remaster_lines(vbf_root, path):
    english, spanish = remaster_paths(vbf_root, path)
    if not (os.path.exists(english) and os.path.exists(spanish)):
        return None
    return paired(lines_of(open(english, 'rb').read()), lines_of(open(spanish, 'rb').read()))


def pal_lines(plain, english_number, spanish_number, count):
    offsets = chunk_offsets(plain, count)
    if not (offsets[english_number] and offsets[spanish_number]):
        return None
    return paired(lines_of(chunk(plain, english_number, count)), lines_of(chunk(plain, spanish_number, count)))


def line_sources(vbf_root, remaster_path, pal, english_number, spanish_number, count):
    return remaster_lines(vbf_root, remaster_path), pal_lines(pal, english_number, spanish_number, count) if pal else None


def english_texts(texts, number, count):
    english = {index: chunk(plain, number, count) for index, plain in texts.items()}
    return {index: text for index, text in english.items() if lines_of(text)}


def disc_codes(english):
    every_line = [line for text in english.values() for line in lines_of(text)]
    buttons, times = params(every_line, CONTROLLER), params(every_line, TIME)
    return lambda line, disc_line: with_disc_codes(line, disc_line, buttons, times)


def spanish_chunks(iso_path, texts, names, sources_for, number, count, charset):
    manual = json.load(open(EVENT_STRINGS))
    space = bytes([FIRST_CHARACTER + charset.index(' ')])
    english = english_texts(texts, number, count)
    remaster_codes = disc_codes(english)
    pal_codes = lambda line, disc_line: line
    found = {index: sources_for(index) for index in english}
    glossaries = [(glossary(remaster for remaster, _ in found.values() if remaster), remaster_codes),
                  (glossary(pal for _, pal in found.values() if pal), pal_codes)]
    replacements, sizes = {}, {}
    for index in english:
        remaster, pal = found[index]
        sources = ([(*remaster, remaster_codes)] if remaster else []) + ([(*pal, pal_codes)] if pal else [])
        disc_lines = lines_of(english[index])
        overrides, untranslated = translated_lines(disc_lines, sources, glossaries, space)
        translation = manual.get(names[index], {})
        overrides |= {int(line): pal[1][pal_line] for line, pal_line in translation.get('pal', {}).items()}
        overrides |= {int(line): encoded(readable, charset) for line, readable in translation.get('text', {}).items()}
        still_english = set(untranslated) - set(overrides)
        for line in sorted(still_english & set(first_numbers(english[index]).values())):
            print('untranslated', names[index], line, json.dumps(decoded(disc_lines[line], charset), ensure_ascii=False))
        if not overrides:
            continue
        rebuilt = replace_last_chunk(texts[index], number, with_strings(english[index], overrides), count)
        replacements[index] = packed_like(iso_path, index, rebuilt)
        sizes[index] = len(rebuilt)
    return replacements, sizes


def by_event(catalog):
    events = {int(index): entry['event'] for index, entry in catalog.items() if entry.get('event')}
    if len(set(events.values())) != len(events):
        raise ValueError('an event name appears in more than one file')
    return events


def remaster_event(event):
    return f'event/obj_ps3/{event[:2]}/{event}/{event}.bin'


def spanish_for_missing_english(iso_path, vbf_root, events, plains, english, adapt):
    flags = lambda text: [header & ~OFFSET_MASK for header in headers(text)]
    replacements, sizes = {}, {}
    for index, plain in plains.items():
        english_path, spanish_path = remaster_paths(vbf_root, remaster_event(events[index]))
        if index in english or not chunk_offsets(plain)[LOCAL_TEXT] or not os.path.exists(spanish_path):
            continue
        remaster_english, remaster_spanish, local = open(english_path, 'rb').read(), open(spanish_path, 'rb').read(), chunk(plain, LOCAL_TEXT)
        if remaster_english == remaster_spanish or flags(remaster_spanish) != flags(local):
            continue
        local_lines = lines_of(local)
        payload = with_strings(remaster_spanish, {number: adapt(line, local_lines[number]) for number, line in enumerate(lines_of(remaster_spanish))})
        rebuilt = replace_last_chunk(plain, ENGLISH_TEXT, payload)
        replacements[index] = packed_like(iso_path, index, rebuilt)
        sizes[index] = len(rebuilt)
        print('added english text', events[index], len(local_lines))
    return replacements, sizes


def spanish_events(iso_path, pal_path, vbf_root, catalog, pal_catalog, charset):
    events = by_event(catalog)
    pal_indexes = {event: index for index, event in by_event(pal_catalog).items()}
    plains = {index: plain for index, _, plain in unpacked_files(iso_path, events)}
    texts = {index: plain for index, plain in plains.items() if chunk_offsets(plain)[ENGLISH_TEXT]}
    pal_plains = {index: plain for index, _, plain in unpacked_files(pal_path, {pal_indexes[events[index]] for index in texts if events[index] in pal_indexes})}

    def sources_for(index):
        event = events[index]
        return line_sources(vbf_root, remaster_event(event), pal_plains.get(pal_indexes.get(event)),
                            ENGLISH_TEXT, LOCAL_TEXT, EVENT_CHUNK_COUNT)
    replacements, sizes = spanish_chunks(iso_path, texts, events, sources_for, ENGLISH_TEXT, EVENT_CHUNK_COUNT, charset)
    english = english_texts(texts, ENGLISH_TEXT, EVENT_CHUNK_COUNT)
    added, added_sizes = spanish_for_missing_english(iso_path, vbf_root, events, plains, english, disc_codes(english))
    return replacements | added, sizes | added_sizes


def is_battle(plain):
    return (len(plain) >= CHUNK_TABLE + BATTLE_CHUNK_COUNT * HEADER_WORD and plain[:HEADER_WORD] == BATTLE_CHUNK_COUNT.to_bytes(HEADER_WORD, 'little')
            and chunk_offsets(plain, BATTLE_CHUNK_COUNT)[-1] == len(plain))


def scripted_files(iso_path):
    return {index: (event_script_id(plain), plain) for index, _, plain in unpacked_files(iso_path) if is_battle(plain)}


def is_monster(name):
    return name.isdigit()


def spanish_battles(iso_path, vbf_root, charset, scripted, pal_scripted):
    texts, names = {}, {}
    for index, (name, plain) in scripted.items():
        if not is_monster(name) and chunk_offsets(plain, BATTLE_CHUNK_COUNT)[BATTLE_ENGLISH_TEXT]:
            texts[index], names[index] = plain, name
    pal_battles = {name: plain for name, plain in pal_scripted.values() if not is_monster(name)}

    def sources_for(index):
        battle = names[index]
        return line_sources(vbf_root, f'battle/btl/{battle}/{battle}.bin', pal_battles.get(battle),
                            BATTLE_ENGLISH_TEXT, PAL_BATTLE_LOCAL_TEXT, BATTLE_CHUNK_COUNT)
    return spanish_chunks(iso_path, texts, names, sources_for, BATTLE_ENGLISH_TEXT, BATTLE_CHUNK_COUNT, charset)


def spanish_monsters(iso_path, vbf_root, scripted, scratch):
    tables = {}
    for path in glob.glob(f'{vbf_root}/{SPANISH}/battle/kernel/{MONSTER_TABLES}'):
        _, _, first, last, *_ = struct.unpack_from(STRING_TABLE_FIELDS, open(path, 'rb').read())
        tables |= {number: path for number in range(first, last + 1)}
    os.makedirs(scratch, exist_ok=True)
    arguments, outputs = [], {}
    for index, (name, plain) in sorted(scripted.items()):
        if not is_monster(name):
            continue
        disc_copy = f'{scratch}/{index}_{name}.bin'
        open(disc_copy, 'wb').write(chunk(plain, BATTLE_ENGLISH_TEXT, BATTLE_CHUNK_COUNT))
        arguments += [os.path.relpath(disc_copy, vbf_root), os.path.relpath(tables[int(name)], vbf_root), name, os.path.relpath(f'{disc_copy}.es', vbf_root)]
        outputs[index] = plain, f'{disc_copy}.es'
    run_java_splice(MONSTER_SPLICE, arguments, vbf_root)
    replacements, sizes = {}, {}
    for index, (plain, path) in outputs.items():
        rebuilt = replace_last_chunk(plain, BATTLE_ENGLISH_TEXT, open(path, 'rb').read(), BATTLE_CHUNK_COUNT)
        replacements[index] = packed_like(iso_path, index, rebuilt)
        sizes[index] = len(rebuilt)
    return replacements, sizes


def spanish_macros(iso_path, vbf_root, catalog):
    index = next(int(i) for i, entry in catalog.items() if ENGLISH_MACROS in (entry.get('path'), entry.get('similar')))
    disc = split(read_file(iso_path, index), MACRO_CHUNKS)
    spanish = split(open(f'{vbf_root}/{SPANISH}/menu/macrodic.dcp', 'rb').read(), MACRO_CHUNKS)
    merged = [disc[number] if number == DISC_ONLY_MACRO_CHUNK else spanish[number] for number in range(MACRO_CHUNKS)]
    data = join(merged)
    return {index: pad_to_unit(data)}, {index: len(data)}


def latin_font_files(iso_path):
    fonts, glyph_maps = {}, {}
    for index, plain in uncompressed_starting_with(iso_path, (FONT_MAGIC, GLYPH_MAP_START)):
        if plain.startswith(FONT_MAGIC) and plain[FONT_KIND] == BASE_FONT_KIND:
            fonts[index] = plain
        elif plain.startswith(GLYPH_MAP_START) and len(plain) == LATIN_GLYPH_MAP_SIZE:
            glyph_maps[index] = plain
    return fonts, glyph_maps


def only_distinct(files, what):
    distinct = set(files.values())
    if len(distinct) != 1:
        raise ValueError(f'expected one distinct PAL {what}, found {len(distinct)}')
    return distinct.pop()


def pal_font(iso_path, pal_path):
    pal_fonts, pal_maps = latin_font_files(pal_path)
    pal = only_distinct(pal_fonts, 'base font')
    pal_map = only_distinct(pal_maps, 'glyph map')
    fonts, glyph_maps = latin_font_files(iso_path)
    replacements, sizes = {}, {}
    for index, plain in fonts.items():
        if plain[:FONT_HEADER] != pal[:FONT_HEADER] or len(plain) != len(pal):
            raise ValueError(f'base font {index} layout differs from PAL font')
        replacements[index] = pad_to_unit(pal)
        sizes[index] = len(pal)
    for index in glyph_maps:
        replacements[index] = pad_to_unit(pal_map)
        sizes[index] = len(pal_map)
    return replacements, sizes


def english_kernel_slots(catalog):
    paths = lambda entry: entry.get('paths') or [entry.get('path') or entry.get('similar') or '']
    japanese = {int(index): catalog_name(entry) for index, entry in catalog.items() if entry and paths(entry)[0].startswith(JAPANESE_KERNEL) and len(paths(entry)) == 1}
    english = {int(index): catalog_name(entry) for index, entry in catalog.items() if entry and any(path.startswith(ENGLISH_KERNEL) for path in paths(entry))}
    japanese_by_name = {name: index for index, name in japanese.items()}
    pairs = sorted((japanese_by_name[name], index) for index, name in english.items() if name in japanese_by_name)
    by_offset = {}
    for japanese_index, english_index in pairs:
        by_offset.setdefault(english_index - japanese_index, []).append(japanese_index)
    slots = {}
    for index, name in english.items():
        slots.setdefault(name, set()).add(index)
    for offset, members in by_offset.items():
        if len(members) < MIN_BLOCK_PAIRS:
            continue
        for japanese_index in range(min(members), max(members) + 1):
            if japanese_index in japanese and str(japanese_index + offset) in catalog:
                slots.setdefault(japanese[japanese_index], set()).add(japanese_index + offset)
    return slots


def spanish_kernel(iso_path, vbf_root, kernel_slots, scratch):
    os.makedirs(scratch, exist_ok=True)
    arguments, outputs = [], {}
    for name, indexes in sorted(kernel_slots.items()):
        spanish = f'{vbf_root}/{SPANISH}/battle/kernel/{name}'
        if name not in KERNEL_SPLICEABLE or not os.path.exists(spanish):
            continue
        for index in sorted(indexes):
            disc_copy = f'{scratch}/{index}_{name}'
            open(disc_copy, 'wb').write(decompress(read_file(iso_path, index)))
            arguments += [os.path.relpath(path, vbf_root) for path in (disc_copy, spanish, f'{disc_copy}.es')]
            outputs[index] = f'{disc_copy}.es'
    run_java_splice(KERNEL_SPLICE, [KERNEL_STRINGS, *arguments], vbf_root)
    replacements, sizes = {}, {}
    for index, path in outputs.items():
        plain = open(path, 'rb').read()
        replacements[index] = packed_like(iso_path, index, plain)
        sizes[index] = len(plain)
    return replacements, sizes


def string_table(data):
    _, _, first, last, entry_size, entries_length, start = struct.unpack_from(STRING_TABLE_FIELDS, data)
    words = struct.unpack_from(f'<{(last - first + 1) * entry_size // 2}H', data, start)
    text = start + entries_length
    strings = []
    for offset, width in zip(words[::2], words[1::2]):
        end = data.find(0, text + offset)
        strings.append((data[text + offset:end if end != -1 else len(data)], width))
    return strings


def merged_string_table(disc, translations):
    start = struct.unpack_from(STRING_TABLE_FIELDS, disc)[-1]
    words, body = [], b''
    for candidates in zip(*map(string_table, translations), string_table(disc), strict=True):
        string, width = next((candidate for candidate in candidates if candidate[0]), candidates[-1])
        words += [len(body), width]
        body += string + b'\0'
    return disc[:start] + struct.pack(f'<{len(words)}H', *words) + body


def pal_counterparts(catalog, pal_catalog, names):
    unique = lambda files: {entry['paths'][0]: int(index) for index, entry in files.items() if entry and len(entry.get('paths', [])) == 1}
    japanese, pal = unique(catalog), unique(pal_catalog)
    shifts = sorted((japanese[path], pal[path] - japanese[path]) for path in japanese.keys() & pal.keys())
    counterparts = {}
    for name in names:
        index = japanese.get(JAPANESE_KERNEL + name)
        if index is None:
            continue
        before = [shift for anchor, shift in shifts if anchor < index][-1:]
        after = [shift for anchor, shift in shifts if anchor > index][:1]
        if before and before == after:
            counterparts[name] = index + before[0]
    return counterparts


def spanish_string_tables(iso_path, pal_path, vbf_root, kernel_slots, pal_tables):
    replacements, sizes = {}, {}
    for name, indexes in sorted(kernel_slots.items()):
        spanish_path = f'{vbf_root}/{SPANISH}/battle/kernel/{name}'
        if name not in STRING_TABLES or not os.path.exists(spanish_path):
            continue
        translations = [open(spanish_path, 'rb').read()] + ([decompress(read_file(pal_path, pal_tables[name]))] if name in pal_tables else [])
        for index in sorted(indexes):
            packed = read_file(iso_path, index)
            disc = decompress(packed)
            if any(disc[:STRING_TABLE_HEADER] != translation[:STRING_TABLE_HEADER] for translation in translations):
                raise ValueError(f'string table {name} at {index} header differs from a translation')
            merged = merged_string_table(disc, translations)
            replacements[index] = pad_to_unit(compress(merged, packed[0]))
            sizes[index] = len(merged)
    return replacements, sizes


def catalog_path(entry):
    return (entry.get('path') or entry.get('similar') if entry else None) or ''


def catalog_name(entry):
    path = catalog_path(entry)
    return path.rsplit('/', 1)[-1] if path else None


def set_starts(catalog, second_file):
    return sorted(int(index) - 1 for index, entry in catalog.items() if catalog_name(entry) == second_file)


def menu_sets(catalog):
    return [range(start, start + MENU_SET_LENGTH) for start in set_starts(catalog, MENU_SET_SECOND_FILE)]


def named_set(catalog, reference_names, indexes):
    names = {}
    for offset, index in enumerate(indexes):
        entry = catalog.get(str(index)) or {}
        name = catalog_name(entry)
        known = {path.rsplit('/', 1)[-1] for path in entry.get('paths', [])} | ({name} if name else set())
        if known and reference_names[offset] and reference_names[offset] not in known:
            raise ValueError(f'file set misaligned at {index}: {known} vs {reference_names[offset]}')
        names[reference_names[offset]] = index
    return names


def palette_position(color, width):
    low, high = CSM1_SWAPPED_BITS
    if bool(color & low) != bool(color & high):
        color ^= low | high
    row, column = divmod(color, PALETTE_SIDE)
    return row * width + column


def palette_colors(palettes, width=MENU_PALETTES_WIDTH):
    return [palettes[position * COLOR_BYTES:(position + 1) * COLOR_BYTES] for position in (palette_position(color, width) for color in range(PALETTE_COLORS))]


def nearest_color(colors, wanted):
    return min(range(len(colors)), key=lambda color: sum(abs(a - b) for a, b in zip(colors[color], wanted)))


def with_disc_gil_label(pal, pal_palettes, disc, disc_palettes):
    merged = bytearray(pal)
    pal_colors = palette_colors(pal_palettes)
    nearest_pal = [nearest_color(pal_colors, wanted) for wanted in palette_colors(disc_palettes)]
    for row in GIL_LABEL_ROWS:
        for column in GIL_LABEL_COLUMNS:
            offset = row * MESSAGE_WINDOW_WIDTH + column
            merged[offset] = nearest_pal[disc[offset]]
    return bytes(merged)


def with_cross_circle_from(pal, disc):
    merged = bytearray(pal)
    first, last = CROSS_CIRCLE_COLUMNS.start // ICON_PIXELS_PER_BYTE, CROSS_CIRCLE_COLUMNS.stop // ICON_PIXELS_PER_BYTE
    for row in CROSS_CIRCLE_ROWS:
        offset = row * ICONS_ROW_BYTES
        merged[offset + first:offset + last] = disc[offset + first:offset + last]
    return bytes(merged)


def pal_menu_set(iso_path, pal_path, catalog, pal_catalog, vbf_root):
    japanese_set, english_set = menu_sets(catalog)
    reference = [catalog_name(catalog.get(str(index))) for index in japanese_set]
    english = {name: index for name, index in named_set(catalog, reference, english_set).items() if str(index) in catalog}
    spanish = named_set(pal_catalog, reference, menu_sets(pal_catalog)[0])
    japanese = named_set(catalog, reference, japanese_set)
    targets = [(name, english) for name in PAL_MENU_FILES] + [(name, japanese) for name in PAL_JAPANESE_MODE_FILES]
    replacements, sizes = {}, {}
    pal_palettes = read_file(pal_path, spanish[MENU_PALETTES])
    for name, disc_set in targets:
        index = disc_set[name]
        data = read_file(pal_path, spanish[name])
        if name == MESSAGE_WINDOW:
            data = with_disc_gil_label(data, pal_palettes, read_file(iso_path, index), read_file(iso_path, disc_set[MENU_PALETTES]))
        if name == ICONS and disc_set is english:
            data = with_cross_circle_from(data, read_file(iso_path, japanese[ICONS]))
        replacements[index] = pad_to_unit(data)
        sizes[index] = len(data)
    help_text = open(f'{vbf_root}/{SPANISH}/menu/menumain.bin', 'rb').read()
    replacements[english[MENU_HELP_TEXT]] = pad_to_unit(help_text)
    sizes[english[MENU_HELP_TEXT]] = len(help_text)
    return replacements, sizes


def texture_records(plain):
    records, offset = [], 0
    while offset + TEXTURE_RECORD.size <= len(plain):
        width, height, kind, size = TEXTURE_RECORD.unpack_from(plain, offset)
        if kind in BYTES_PER_PIXEL and width and height and size == width * height * BYTES_PER_PIXEL[kind] + QWORD:
            records.append((offset, width, height, kind))
            offset += TEXTURE_RECORD.size + size
        else:
            offset += QWORD
    return records


def pictures(plain):
    records = texture_records(plain)
    return [(offset + TEXTURE_HEADER, width * height, palette + TEXTURE_HEADER, palette_width)
            for (offset, width, height, kind), (palette, palette_width, _, palette_kind) in zip(records, records[1:])
            if kind == INDEXED and palette_kind == RGBA]


def screen_pictures(plain):
    found = pictures(plain)
    return [picture for picture in found if picture[1] == found[0][1]]


def picture_colors(plain, picture):
    pixels, count, palette, palette_width = picture
    colors = palette_colors(plain[palette:palette + PALETTE_COLORS * COLOR_BYTES], palette_width)
    return colors, [colors[color] for color in plain[pixels:pixels + count]]


def map_layout(plain, length):
    layout = bytearray(plain[:length])
    for field in PICTURE_DEPENDENT_FIELDS:
        layout[field:field + FIELD_BYTES] = bytes(FIELD_BYTES)
    return layout


def title_map(iso_path, reference, length):
    wanted = map_layout(reference, length)
    matches = [index for index, _, plain in unpacked_files(iso_path, limit=length) if map_layout(plain, length) == wanted]
    if len(matches) != 1:
        raise ValueError(f'expected one title map on {iso_path}, found {matches}')
    return matches[0]


def spanish_title(iso_path, pal_path, vbf_root):
    reference = open(f'{vbf_root}/{MASTER}/{TITLE_MAP}', 'rb').read()
    length = texture_records(reference)[0][0] + TEXTURE_RECORD.size
    index = title_map(iso_path, reference, length)
    plain, pal = decompress(read_file(iso_path, index)), decompress(read_file(pal_path, title_map(pal_path, reference, length)))
    pal_pictures = screen_pictures(pal)
    if len(pal_pictures) != len(PAL_TITLE_PICTURES):
        raise ValueError(f'PAL title map has {len(pal_pictures)} pictures, expected {len(PAL_TITLE_PICTURES)}')
    pal_named = dict(zip(PAL_TITLE_PICTURES, pal_pictures))
    title = pictures(plain)[0]
    colors, shown = picture_colors(plain, title)
    if (colors, shown) != picture_colors(pal, pal_named['international']):
        raise ValueError('disc title picture differs from the PAL International title picture')
    spanish = picture_colors(pal, pal_named['spanish'])[1]
    text = [row * TITLE_WIDTH + column for rows, columns in TITLE_TEXT_AREAS for row in rows for column in columns]
    nearest = {color: nearest_color(colors, color) for color in {spanish[pixel] for pixel in text}}
    patched = bytearray(plain)
    for pixel in text:
        patched[title[0] + pixel] = nearest[spanish[pixel]]
    return {index: packed_like(iso_path, index, bytes(patched))}, {index: len(patched)}


def help_sets(iso_path, catalog):
    spans = iso_spans(iso_path)
    starts = set_starts(catalog, HELP_SET_SECOND_FILE)
    sets = []
    for start, next_start in zip(starts, starts[1:] + [len(spans)]):
        end = start
        while end < next_start and spans[end] and not read_file(iso_path, end).startswith(FONT_MAGIC):
            end += 1
        sets.append(range(start, end))
    return sets


def pal_help_set(iso_path, pal_path, catalog, pal_catalog):
    path = lambda index: catalog_path(catalog.get(str(index)))
    sets = help_sets(iso_path, catalog)
    english_set, = [indexes for indexes in sets if path(indexes[0]).startswith(ENGLISH_HELP)]
    japanese_set, = [indexes for indexes in sets if path(indexes[0]).startswith(JAPANESE_HELP)]
    spanish_set, = help_sets(pal_path, pal_catalog)
    if len(english_set) != len(spanish_set):
        raise ValueError(f'help sets differ in length: {len(english_set)} vs {len(spanish_set)}')
    for disc_indexes in (english_set, japanese_set):
        named_set(pal_catalog, [catalog_name(catalog.get(str(index))) for index in disc_indexes], spanish_set[:len(disc_indexes)])
    textures = [(index, pal_index) for index, pal_index in zip(japanese_set, spanish_set) if path(index).startswith(JAPANESE_HELP + HELP_TEXTURES)]
    spans, pal_spans = iso_spans(iso_path), iso_spans(pal_path)
    replacements, sizes = {}, {}
    for index, pal_index in [*zip(english_set, spanish_set), *textures]:
        if spans[index][2] != pal_spans[pal_index][2]:
            raise ValueError(f'help file {index} and PAL {pal_index} differ in compression')
        data = read_file(pal_path, pal_index)
        replacements[index] = pad_to_unit(data)
        sizes[index] = pal_catalog[str(pal_index)]['size']
    return replacements, sizes


def main(iso_path, pal_path, vbf_root, catalog_path, pal_catalog_path, output_path):
    catalog = json.load(open(catalog_path))
    charset = open(f'{vbf_root}/{MASTER}/{CHARSET}', encoding='utf-8').read()
    kernel_slots = english_kernel_slots(catalog)
    pal_catalog = json.load(open(pal_catalog_path))
    print('  Reading battle scripts')
    scripted = scripted_files(iso_path)
    parts = (
        ('event text', lambda: spanish_events(iso_path, pal_path, vbf_root, catalog, pal_catalog, charset)),
        ('battle text', lambda: spanish_battles(iso_path, vbf_root, charset, scripted, scripted_files(pal_path))),
        ('monster text', lambda: spanish_monsters(iso_path, vbf_root, scripted, f'{vbf_root}/{MONSTER_SCRATCH}')),
        ('macro dictionary', lambda: spanish_macros(iso_path, vbf_root, catalog)),
        ('font', lambda: pal_font(iso_path, pal_path)),
        ('menus', lambda: pal_menu_set(iso_path, pal_path, catalog, pal_catalog, vbf_root)),
        ('help screens', lambda: pal_help_set(iso_path, pal_path, catalog, pal_catalog)),
        ('title screen', lambda: spanish_title(iso_path, pal_path, vbf_root)),
        ('kernel text', lambda: spanish_kernel(iso_path, vbf_root, kernel_slots, f'{vbf_root}/{KERNEL_SCRATCH}')),
        ('string tables', lambda: spanish_string_tables(iso_path, pal_path, vbf_root, kernel_slots, pal_counterparts(catalog, pal_catalog, STRING_TABLES))))
    replacements, sizes = {}, {}
    for part_replacements, part_sizes in run_steps(parts, '  Building'):
        replacements.update(part_replacements)
        sizes.update(part_sizes)
    print('  Files replaced:', len(replacements))
    print('  Writing the ISO')
    print('  Sectors before/after:', rebuild(iso_path, output_path, replacements, sizes))
    patch_program(output_path)
