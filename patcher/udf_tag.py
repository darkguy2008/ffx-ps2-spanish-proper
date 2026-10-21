import binascii
import struct

TAG_SIZE = 16
CHECKSUM_OFFSET = 4
CRC_OFFSET = 8
LOCATION_OFFSET = 12


def seal(descriptor, location):
    data = bytearray(descriptor)
    crc_length = struct.unpack_from('<H', data, CRC_OFFSET + 2)[0]
    struct.pack_into('<I', data, LOCATION_OFFSET, location)
    struct.pack_into('<H', data, CRC_OFFSET, binascii.crc_hqx(bytes(data[TAG_SIZE:TAG_SIZE + crc_length]), 0))
    data[CHECKSUM_OFFSET] = sum(data[:CHECKSUM_OFFSET] + data[CHECKSUM_OFFSET + 1:TAG_SIZE]) & 0xff
    return bytes(data)
