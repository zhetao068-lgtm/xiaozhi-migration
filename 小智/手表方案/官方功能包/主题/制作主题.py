"""从指定的官方 C6 固件提取资源，仅换配色，生成可单独烧录的资源文件。"""

import hashlib
import json
import struct
from pathlib import Path
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
FIRMWARE = HERE.parents[1] / "固件" / "v2.5.2_waveshare-esp32-c6-lcd-0.85.zip"
OFFICIAL_SHA256 = "b71061de4e8de75427f1aea32eba5900d1e6c1ae356ca631b294a47d18950c9d"
ASSETS_OFFSET = 0x600000
ASSETS_LIMIT = 0x200000
HEADER = struct.Struct("<III")
ENTRY = struct.Struct("<32sIIHH")
MAGIC = b"\x5a\x5a"


def unpack(image):
    count, checksum, size = HEADER.unpack_from(image)
    body = image[HEADER.size:]
    if size != len(body) or checksum != sum(body) & 0xFFFF:
        raise ValueError("资源长度或校验和无效")
    table_size = count * ENTRY.size
    if not 0 < table_size <= size:
        raise ValueError("资源表大小无效")
    assets = {}
    next_offset = 0
    for raw_name, length, offset, width, height in ENTRY.iter_unpack(body[:table_size]):
        name = raw_name.rstrip(b"\0")
        start = table_size + offset
        end = start + len(MAGIC) + length
        if name in assets or offset != next_offset or end > size or body[start:start + 2] != MAGIC:
            raise ValueError("资源名称、偏移或标记无效")
        assets[name] = (body[start + 2:end], width, height)
        next_offset = end - table_size
    if table_size + next_offset != size:
        raise ValueError("资源表未覆盖完整的数据区")
    return assets


def pack(assets):
    table = bytearray()
    data = bytearray()
    for name, (payload, width, height) in assets.items():
        table.extend(ENTRY.pack(name, len(payload), len(data), width, height))
        data.extend(MAGIC)
        data.extend(payload)
    body = table + data
    image = HEADER.pack(len(assets), sum(body) & 0xFFFF, len(body)) + body
    if len(image) > ASSETS_LIMIT or unpack(image) != assets:
        raise ValueError("主题包超出分区大小或回读不一致")
    return image


def main():
    with ZipFile(FIRMWARE) as source:
        firmware = source.read("merged-binary.bin")
    if hashlib.sha256(firmware).hexdigest() != OFFICIAL_SHA256:
        raise ValueError("固件 SHA-256 与指定的官方 C6 版本不符")
    original = firmware[ASSETS_OFFSET:]
    assets = unpack(original)
    old_index, width, height = assets[b"index.json"]
    index = json.loads(old_index)
    index["skin"] = {
        "light": {"text_color": "#12283A", "background_color": "#DDF5F1"},
        "dark": {"text_color": "#ECFAFF", "background_color": "#142B42"},
    }
    assets[b"index.json"] = (json.dumps(index, separators=(",", ":")).encode(), width, height)
    theme = pack(assets)
    for filename, image in (("stock-assets.bin", original), ("study-assets.bin", theme)):
        (HERE / filename).write_bytes(image)
        print(f"{filename}  {len(image)} bytes  SHA256 {hashlib.sha256(image).hexdigest()}")


if __name__ == "__main__":
    main()
