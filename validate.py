#!/usr/bin/python3

import sys
from enum import Enum
import struct
from itertools import islice

class Marker(Enum):
  SOT = (0xFF90)
  SOD = (0xFF93, True)
  EPH = (0xFF92, True)
  SOP = (0xFF91)
  EOC = (0xFFD9, True)
  SOC = (0xFF4F, True)
  SIZ = (0xFF51)
  COD = (0xff52)
  QCD = (0xff5c)
  POC = (0xff5f)
  COM = (0xff64)
  TLM = (0xff55)

  def __new__(cls, marker, is_empty = False):
    obj = object.__new__(cls)
    obj._value_ = marker
    obj.is_empty = is_empty
    return obj

def read_byte(f, p):
  f.seek(p)
  v = f.read(1)
  if len(v) != 1:
    raise "Read error in Tile-Part 1"
  return v[0]

def trigger_positions(main_header_len, tile_part_offset, tile_part_len):
  for p in range(254, main_header_len + tile_part_len, 256):
    yield (p if p < main_header_len else p - main_header_len + tile_part_offset,
           p + 1 if p < main_header_len else p + 1 - main_header_len + tile_part_offset)

def check_tile_part(f, main_header_len, tile_part_offset, tile_part_len):
  for (p1, p2) in trigger_positions(main_header_len, tile_part_offset, tile_part_len):
    if  read_byte(f, p1) == 0xFF and read_byte(f, p2) == 0xFF:
      raise Exception(f"0xFFFF detected at offset {p1}")

def validate(fn):
  f = open(fn, "rb")

  tile_parts_len = []
  main_header_len = 0

  while True:
    marker_bytes = f.read(2)
    if len(marker_bytes) != 2:
      break

    marker = Marker(marker_bytes[0] * 256 + marker_bytes[1])

    if marker is Marker.SOT:
      main_header_len = f.tell() - 2 # subtract the SOT marker length
      break;

    if marker.is_empty:
      continue

    size_field = f.read(2)
    if len(size_field) != 2:
      break
    segment_size = ((size_field[0] << 8) + size_field[1])

    if marker is not Marker.TLM:
      # skip over the marker segment
      f.seek(segment_size - 2, 1)
      continue

    print(f"Found TLM marker segment af position {hex(f.tell() - 2)}")

    if len(tile_parts_len) > 0:
      raise "Multiple TLM marker segments"

    payload = f.read(segment_size - 2)

    # stlm

    st_field = (payload[1] & 0b00110000) >> 4
    sp_field = (payload[1] & 0b01000000) >> 6

    fmt = ">"

    if st_field == 1:
      fmt += "B"
    elif st_field == 2:
      fmt += "H"

    if sp_field == 0:
      fmt += "H"
    else:
      fmt += "L"

    for entry in islice(struct.iter_unpack(fmt, payload[2:]), 3):
      tile_parts_len.append(entry[-1])

  if len(tile_parts_len) != 3:
    raise "Missing or incomplete TLM marker segment"

  print(f"Tile-part lengths: {', '.join(map(str, tile_parts_len))}")

  if main_header_len <= 0:
    raise "Invalid Main Header length"
  print(f"Main header length: {main_header_len}")

  # scan for the forbidden pattern

  # main_header + tile_part_1

  check_tile_part(f, main_header_len, main_header_len, tile_parts_len[0])

  # main_header + tile_part_2

  check_tile_part(f, main_header_len, main_header_len + tile_parts_len[0], tile_parts_len[1])

  # main_header + tile_part_2

  check_tile_part(f, main_header_len, main_header_len + tile_parts_len[0] + tile_parts_len[1], tile_parts_len[2])

if __name__ == "__main__":
    validate(sys.argv[1])