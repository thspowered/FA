from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from PIL import Image


# Štruktúra hlavičky (bity):
#  - type: 1 bit (0 = text, 1 = súbor)
#  - method: 2 bity (0 = každý pixel, 1 = každý párny, 2 = každý nepárny, 3 = okrajové pixely)
#  - filename: 64 bajtov (512 bitov), UTF‑8, ukončené NUL ak je kratší; pri texte sa nepoužíva
#  - first_bit_position: 32 bitov (index prvého pixela použitý pre dáta v zploštenom zozname pixelov)
#  - last_bit_position: 32 bitov (index posledného pixela použitý pre dáta)
#
# Celková veľkosť hlavičky: 1 + 2 + 512 + 32 + 32 = 579 bitov


HEADER_BITS = 1 + 2 + 512 + 32 + 32


@dataclass
class EncodedHeader:
    info_type: int  
    method: int 
    filename_64: bytes 
    first_bit_position: int
    last_bit_position: int

    def to_bits(self) -> List[int]:
        bits: List[int] = []
        bits.append(self.info_type & 1)
        method = self.method & 0b11
        bits.extend([(method >> 1) & 1, method & 1])
        for b in self.filename_64:
            for i in range(7, -1, -1):
                bits.append((b >> i) & 1)
        for value in (self.first_bit_position, self.last_bit_position):
            for i in range(31, -1, -1):
                bits.append((value >> i) & 1)
        assert len(bits) == HEADER_BITS
        return bits

    @staticmethod
    def from_bits(bits: Iterable[int]) -> "EncodedHeader":
        bits = list(bits)
        assert len(bits) >= HEADER_BITS
        idx = 0
        info_type = bits[idx]; idx += 1
        method = (bits[idx] << 1) | bits[idx + 1]; idx += 2
        filename_bytes = bytearray()
        for _ in range(64):
            val = 0
            for i in range(8):
                val = (val << 1) | bits[idx]
                idx += 1
            filename_bytes.append(val)
        def read_u32() -> int:
            nonlocal idx
            v = 0
            for _ in range(32):
                v = (v << 1) | bits[idx]
                idx += 1
            return v
        first_pos = read_u32()
        last_pos = read_u32()
        return EncodedHeader(info_type, method, bytes(filename_bytes), first_pos, last_pos)


def _pad_filename(name: str) -> bytes:
    b = name.encode("utf-8")[:64]
    if len(b) < 64:
        b = b + b"\x00" * (64 - len(b))
    return b


def _image_to_pixels(img: Image.Image) -> Tuple[List[Tuple[int, int, int]], int, int]:
    if img.mode != "RGB":
        img = img.convert("RGB")
    width, height = img.size
    pixels = list(img.getdata()) 
    return pixels, width, height


def _pixels_to_image(pixels: List[Tuple[int, int, int]], size: Tuple[int, int]) -> Image.Image:
    img = Image.new("RGB", size)
    img.putdata(pixels)
    return img


def _eligible_indices(width: int, height: int, method: int) -> List[int]:
    total = width * height
    if method == 0:
        return list(range(total))
    if method == 1:
        return list(range(0, total, 2))
    if method == 2:
        return list(range(1, total, 2))
    if method == 3:
        idxs: List[int] = []
        for y in range(height):
            for x in range(width):
                if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                    idxs.append(y * width + x)
        return idxs
    raise ValueError("Unsupported method")


def _bits_from_bytes(data: bytes) -> List[int]:
    bits: List[int] = []
    for b in data:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits


def _bytes_from_bits(bits: Iterable[int]) -> bytes:
    bits = list(bits)
    if len(bits) % 8 != 0:
        raise ValueError("Bit length must be a multiple of 8")
    out = bytearray()
    for i in range(0, len(bits), 8):
        val = 0
        for j in range(8):
            val = (val << 1) | bits[i + j]
        out.append(val)
    return bytes(out)


def _write_bits_to_pixels(pixels: List[Tuple[int, int, int]], start_idx: int, bit_positions: List[int], bits: List[int]) -> int:
    """Zapíše bity do LSB modrej zložky pixelov.

    Vráti index posledného použitého pixela (v zploštenom poradí).
    """
    last_pos = start_idx
    p = pixels
    bit_i = 0
    for pos in bit_positions:
        if pos < start_idx:
            continue
        if bit_i >= len(bits):
            break
        r, g, b = p[pos]
        b = (b & 0xFE) | bits[bit_i]
        p[pos] = (r, g, b)
        bit_i += 1
        last_pos = pos
    if bit_i != len(bits):
        raise ValueError("Nedostatočná kapacita pre dáta pri zvolenej metóde")
    return last_pos


def _read_bits_from_pixels(pixels: List[Tuple[int, int, int]], bit_positions: List[int], count: int, starting_from: int = 0) -> List[int]:
    bits: List[int] = []
    for pos in bit_positions:
        if pos < starting_from:
            continue
        if len(bits) >= count:
            break
        _, _, b = pixels[pos]
        bits.append(b & 1)
    if len(bits) < count:
        raise ValueError("Nie je dostupný dostatočný počet bitov na čítanie")
    return bits


def _capacity_for_method(width: int, height: int, method: int, reserved_prefix: int = 0) -> int:
    idxs = _eligible_indices(width, height, method)
    usable = [i for i in idxs if i >= reserved_prefix]
    return len(usable)


def _reserve_for_header(pixels: List[Tuple[int, int, int]]) -> List[int]:
    return list(range(HEADER_BITS))


def embed_text(input_bmp: str, output_bmp: str, text: str, method: int = 0) -> None:
    _embed_common(input_bmp, output_bmp, payload=text.encode("utf-8"), info_type=0, method=method, filename="")


def embed_file(input_bmp: str, output_bmp: str, file_path: str, method: int = 0) -> None:
    with open(file_path, "rb") as f:
        data = f.read()
    filename = os.path.basename(file_path)[:64]
    _embed_common(input_bmp, output_bmp, payload=data, info_type=1, method=method, filename=filename)


def _embed_common(input_bmp: str, output_bmp: str, payload: bytes, info_type: int, method: int, filename: str) -> None:
    img = Image.open(input_bmp)
    pixels, width, height = _image_to_pixels(img)

    payload_len = len(payload)
    if payload_len > 0xFFFFFFFF:
        raise ValueError("Dáta sú príliš veľké")
    length_bytes = payload_len.to_bytes(4, byteorder="big")
    payload_bits = _bits_from_bytes(length_bytes + payload)

    header_reserved = HEADER_BITS
    total_capacity = width * height
    if total_capacity < header_reserved:
        raise ValueError("Obrázok je príliš malý na uloženie hlavičky")
    method_capacity = _capacity_for_method(width, height, method, reserved_prefix=header_reserved)
    if method_capacity < len(payload_bits):
        raise ValueError(f"Nedostatočná kapacita. Potrebných {len(payload_bits)} bitov, dostupných {method_capacity} bitov")

    header_positions = _reserve_for_header(pixels)
    data_positions = _eligible_indices(width, height, method)

    data_positions_after_header = [i for i in data_positions if i >= header_reserved]
    first_pos = data_positions_after_header[0]
    last_pos = data_positions_after_header[len(payload_bits) - 1]

    header = EncodedHeader(
        info_type=info_type,
        method=method,
        filename_64=_pad_filename(filename if info_type == 1 else ""),
        first_bit_position=first_pos,
        last_bit_position=last_pos,
    )

    header_bits = header.to_bits()
    _write_bits_to_pixels(pixels, 0, header_positions, header_bits)

    _write_bits_to_pixels(pixels, header_reserved, data_positions, payload_bits)

    out_img = _pixels_to_image(pixels, (width, height))
    out_img.save(output_bmp, format="BMP")


def extract(input_bmp: str) -> Tuple[str, bytes | None, str | None]:
    """Extrahuje skryté dáta z BMP.

    Vracia trojicu: (typ, dáta, názov súboru)
      - typ == "text" => dáta sú bajty UTF‑8 (volajúci si ich môže dekódovať)
      - typ == "file" => dáta sú surové bajty a názov súboru je priložený (môže byť prázdny)
    """
    img = Image.open(input_bmp)
    pixels, width, height = _image_to_pixels(img)

    header_positions = _reserve_for_header(pixels)
    header_bits = _read_bits_from_pixels(pixels, header_positions, HEADER_BITS)
    header = EncodedHeader.from_bits(header_bits)

    method_positions = _eligible_indices(width, height, header.method)
    length_bits = _read_bits_from_pixels(pixels, method_positions, 32, starting_from=max(header.first_bit_position, HEADER_BITS))
    payload_len = int.from_bytes(_bytes_from_bits(length_bits), byteorder="big")
    total_bits = 32 + payload_len * 8
    payload_bits = _read_bits_from_pixels(pixels, method_positions, total_bits, starting_from=max(header.first_bit_position, HEADER_BITS))
    payload_bytes = _bytes_from_bits(payload_bits)[4:]

    if header.info_type == 0:
        return "text", payload_bytes, None
    else:
        fname = header.filename_64.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
        return "file", payload_bytes, fname or None


__all__ = [
    "embed_text",
    "embed_file",
    "extract",
]


