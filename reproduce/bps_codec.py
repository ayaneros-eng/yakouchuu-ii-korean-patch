#!/usr/bin/env python3
"""Create and self-verify a compact BPS1 patch for the Yakouchuu II ROM.

The encoder intentionally uses only SourceRead, TargetRead and TargetCopy.
Long zero runs in the expanded 64 MiB target are represented by a one-byte
literal followed by an overlapping TargetCopy, keeping the patch compact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from collections import Counter
from pathlib import Path


SOURCE_READ = 0
TARGET_READ = 1
SOURCE_COPY = 2
TARGET_COPY = 3


def encode_number(value: int) -> bytes:
    if value < 0:
        raise ValueError(value)
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0:
            output.append(byte | 0x80)
            return bytes(output)
        output.append(byte)
        value -= 1


def decode_number(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    shift = 1
    while True:
        byte = data[position]
        position += 1
        value += (byte & 0x7F) * shift
        if byte & 0x80:
            return value, position
        shift <<= 7
        value += shift


def encode_signed(delta: int) -> bytes:
    return encode_number((abs(delta) << 1) | (1 if delta < 0 else 0))


def decode_signed(data: bytes, position: int) -> tuple[int, int]:
    value, position = decode_number(data, position)
    magnitude = value >> 1
    return (-magnitude if value & 1 else magnitude), position


def sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def equal_run(source: bytes, target: bytes, position: int) -> int:
    limit = min(len(source), len(target))
    end = position
    while end < limit and source[end] == target[end]:
        end += 1
    return end - position


def zero_run(target: bytes, position: int) -> int:
    end = target.find(b"\x01", position)  # fast path is not valid for arbitrary nonzero bytes
    del end
    cursor = position
    limit = len(target)
    while cursor < limit and target[cursor] == 0:
        cursor += 1
    return cursor - position


def make_patch(source: bytes, target: bytes) -> tuple[bytes, Counter[str]]:
    patch = bytearray(b"BPS1")
    patch.extend(encode_number(len(source)))
    patch.extend(encode_number(len(target)))
    patch.extend(encode_number(0))
    position = 0
    target_relative = 0
    stats: Counter[str] = Counter()

    def action(kind: int, length: int) -> None:
        if length < 1:
            raise ValueError(length)
        patch.extend(encode_number(((length - 1) << 2) | kind))
        stats[{SOURCE_READ: "SourceRead", TARGET_READ: "TargetRead", TARGET_COPY: "TargetCopy"}[kind]] += 1
        stats[{SOURCE_READ: "SourceRead_bytes", TARGET_READ: "TargetRead_bytes", TARGET_COPY: "TargetCopy_bytes"}[kind]] += length

    while position < len(target):
        same = equal_run(source, target, position) if position < len(source) else 0
        if same:
            action(SOURCE_READ, same)
            position += same
            continue

        zeros = zero_run(target, position) if target[position] == 0 else 0
        if zeros >= 16:
            # Seed one literal zero at the current output position, then copy
            # from that byte with overlap to repeat it for the rest of the run.
            action(TARGET_READ, 1)
            patch.append(0)
            stats["literal_bytes"] += 1
            anchor = position
            position += 1
            remaining = zeros - 1
            action(TARGET_COPY, remaining)
            patch.extend(encode_signed(anchor - target_relative))
            target_relative = anchor + remaining
            position += remaining
            continue

        start = position
        position += 1
        while position < len(target):
            if position < len(source) and equal_run(source, target, position) >= 8:
                break
            if target[position] == 0 and zero_run(target, position) >= 16:
                break
            position += 1
        literal = target[start:position]
        action(TARGET_READ, len(literal))
        patch.extend(literal)
        stats["literal_bytes"] += len(literal)

    patch.extend(struct.pack("<I", zlib.crc32(source) & 0xFFFFFFFF))
    patch.extend(struct.pack("<I", zlib.crc32(target) & 0xFFFFFFFF))
    patch.extend(struct.pack("<I", zlib.crc32(patch) & 0xFFFFFFFF))
    return bytes(patch), stats


def apply_patch(source: bytes, patch: bytes) -> bytes:
    if patch[:4] != b"BPS1":
        raise ValueError("not a BPS1 patch")
    if zlib.crc32(patch[:-4]) & 0xFFFFFFFF != struct.unpack_from("<I", patch, len(patch) - 4)[0]:
        raise ValueError("patch CRC mismatch")
    position = 4
    source_size, position = decode_number(patch, position)
    target_size, position = decode_number(patch, position)
    metadata_size, position = decode_number(patch, position)
    if source_size != len(source):
        raise ValueError("source size mismatch")
    position += metadata_size
    output = bytearray()
    source_relative = 0
    target_relative = 0
    action_end = len(patch) - 12
    while len(output) < target_size:
        if position >= action_end:
            raise ValueError("actions ended before target was complete")
        command, position = decode_number(patch, position)
        kind = command & 3
        length = (command >> 2) + 1
        if kind == SOURCE_READ:
            start = len(output)
            output.extend(source[start : start + length])
        elif kind == TARGET_READ:
            output.extend(patch[position : position + length])
            position += length
        elif kind == SOURCE_COPY:
            delta, position = decode_signed(patch, position)
            source_relative += delta
            output.extend(source[source_relative : source_relative + length])
            source_relative += length
        elif kind == TARGET_COPY:
            delta, position = decode_signed(patch, position)
            target_relative += delta
            for _ in range(length):
                output.append(output[target_relative])
                target_relative += 1
        if len(output) > target_size:
            raise ValueError("action overran target size")
    if position != action_end:
        raise ValueError("unused bytes before footer")
    source_crc, target_crc = struct.unpack_from("<II", patch, action_end)
    if zlib.crc32(source) & 0xFFFFFFFF != source_crc:
        raise ValueError("source CRC mismatch")
    if zlib.crc32(output) & 0xFFFFFFFF != target_crc:
        raise ValueError("target CRC mismatch")
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    target = args.target.read_bytes()
    patch, stats = make_patch(source, target)
    rebuilt = apply_patch(source, patch)
    if rebuilt != target:
        raise SystemExit("self-verification failed: rebuilt target differs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    report = {
        "schema": "yak2_bps_patch_v1",
        "source": str(args.source.resolve()),
        "source_size": len(source),
        "source_sha256": sha256(source),
        "target": str(args.target.resolve()),
        "target_size": len(target),
        "target_sha256": sha256(target),
        "patch": str(args.output.resolve()),
        "patch_size": len(patch),
        "patch_sha256": sha256(patch),
        "compression_ratio_to_target": round(len(patch) / len(target), 6),
        "actions": dict(sorted(stats.items())),
        "self_apply_exact": True,
        "source_crc32": f"{zlib.crc32(source) & 0xFFFFFFFF:08X}",
        "target_crc32": f"{zlib.crc32(target) & 0xFFFFFFFF:08X}",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
