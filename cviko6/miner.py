#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


OUTPUT_FILE = Path("blocks.txt")
BLOCK_COUNT = 5
DIFFICULTIES = [2, 3, 4, 3, 2]


def sha256_hex(payload: str) -> str:
    """Vrátí SHA-256 hex digest daného reťazca payload."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class Block:
    height: int
    prev_hash: str
    data_raw: int
    data_hash: str
    difficulty: int
    nonce: int
    block_hash: str


def mine_block(data_hash: str, prev_hash: str, difficulty: int, rng: random.Random) -> Tuple[int, str]:
    """Vykopajte nonce, ktorý spĺňa obmedzenie obtiažnosti a vráťte jeho hash."""
    prefix = "0" * difficulty
    base = (data_hash + prev_hash).encode("utf-8")
    nonce = rng.randrange(0, 1_000_000_000)

    while True:
        block_hash = hashlib.sha256(base + str(nonce).encode("utf-8")).hexdigest()
        if block_hash.startswith(prefix):
            return nonce, block_hash
        nonce += 1


def build_chain(count: int, difficulties: List[int]) -> List[Block]:
    """Vytvorte zoznam blokov, ktoré boli vykopané."""
    if len(difficulties) < count:
        raise ValueError("Nedostatočné počet obtiažností pre požadovaný počet blokov.")

    blocks: List[Block] = []
    prev_hash = "-"
    rng = random.SystemRandom()

    for height in range(count):
        data_raw = rng.randrange(0, 1_000_000)
        data_hash = sha256_hex(str(data_raw))
        difficulty = difficulties[height]
        nonce, block_hash = mine_block(
            data_hash, prev_hash if prev_hash != "-" else "", difficulty, rng
        )

        block = Block(
            height=height,
            prev_hash=prev_hash,
            data_raw=data_raw,
            data_hash=data_hash,
            difficulty=difficulty,
            nonce=nonce,
            block_hash=block_hash,
        )
        blocks.append(block)
        prev_hash = block_hash

    return blocks


def format_block(block: Block) -> str:
    """Vráti textové vyjadrenie bloku v požadovanom formáte."""
    lines = [
        f"Výška bloku: {block.height}",
        f"Hash bloku: {block.block_hash}",
        f"Hash předchozího: {block.prev_hash}",
        f"Data: {block.data_hash} -> Hash(Data RAW)",
        f"Data RAW: {block.data_raw} -> (Random cislo)",
        f"Nonce: {block.nonce}",
        f"Obtížnost: {block.difficulty}",
    ]
    return "\n".join(lines)


def write_blocks(blocks: List[Block]) -> None:
    """Zapíšte všetky bloky do výstupného textového súboru."""
    sections = [format_block(block) for block in blocks]
    OUTPUT_FILE.write_text("\n\n".join(sections) + "\n", encoding="utf-8")


def main() -> None:
    """Hlavná funkcia programu."""
    blocks = build_chain(BLOCK_COUNT, DIFFICULTIES)
    write_blocks(blocks)


if __name__ == "__main__":
    main()
