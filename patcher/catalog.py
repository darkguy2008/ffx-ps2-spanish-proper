import functools, hashlib, os, struct

from tqdm import tqdm

from disc_table import SECTOR, iso_spans
from ffx_codec import decompress

EVENT_MAGIC = b'EV01'
HEADER_PROBE = 64
SCRIPT_ID_FIELD = 0x0C


def unpacked_files(iso_path, indexes=None, limit=None):
    spans = [(index, span) for index, span in enumerate(iso_spans(iso_path)) if span and (indexes is None or index in indexes)]
    with open(iso_path, 'rb') as iso:
        for index, (lba, size, compressed) in tqdm(spans, desc=f'Reading {os.path.basename(iso_path)}', unit='file', leave=False):
            iso.seek(lba * SECTOR)
            data = iso.read(size)
            yield index, compressed, decompress(data, limit) if compressed else data[:limit]


def event_script_id(plain):
    script_start = struct.unpack_from('<I', plain, 4)[0]
    id_address = script_start + struct.unpack_from('<I', plain, script_start + SCRIPT_ID_FIELD)[0]
    return plain[id_address:plain.index(b'\0', id_address)].decode('ascii')


@functools.cache
def reference_indexes(master_root, folders):
    hashes, shapes = {}, {}
    paths = [os.path.join(directory, name) for folder in folders for directory, _, names in os.walk(os.path.join(master_root, folder)) for name in names]
    for path in tqdm(paths, desc='Reading remaster files', unit='file', leave=False):
        data = open(path, 'rb').read()
        relative = os.path.relpath(path, master_root)
        hashes.setdefault(hashlib.sha1(data).digest(), []).append(relative)
        shapes.setdefault((len(data), data[:HEADER_PROBE]), []).append(relative)
    return hashes, shapes


def build(iso_path, master_root, folders):
    hashes, shapes = reference_indexes(master_root, folders)
    catalog = {}
    for index, compressed, plain in unpacked_files(iso_path):
        entry = {'compressed': compressed, 'size': len(plain)}
        paths = hashes.get(hashlib.sha1(plain).digest())
        similar = shapes.get((len(plain), plain[:HEADER_PROBE]), [])
        if paths:
            entry['path'] = paths[0]
            entry['paths'] = paths
        elif len(set(similar)) == 1:
            entry['similar'] = similar[0]
        if plain[:4] == EVENT_MAGIC:
            entry['event'] = event_script_id(plain)
        catalog[index] = entry
    return catalog


def uncompressed_starting_with(iso_path, prefixes):
    probe = max(map(len, prefixes))
    with open(iso_path, 'rb') as iso:
        for index, span in enumerate(iso_spans(iso_path)):
            if not span or span[2]:
                continue
            iso.seek(span[0] * SECTOR)
            if iso.read(probe).startswith(prefixes):
                iso.seek(span[0] * SECTOR)
                yield index, iso.read(span[1])
