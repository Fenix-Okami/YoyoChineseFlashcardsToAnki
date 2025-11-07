#!/usr/bin/env python3
"""Enrichment step: ensure audio + generate rich.tsv files."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Iterable, List

from . import common

AUDIO_SPEED = "normal"


def _load_cards(cards_path: str) -> List[common.Flashcard]:
    with open(cards_path, "r", encoding="utf-8") as handle:
        raw_cards = json.load(handle)
    cards: List[common.Flashcard] = []
    for raw in raw_cards:
        cards.append(
            common.Flashcard(
                id=str(raw.get("id", "")),
                code=raw.get("code") or "",
                masteryLevel=raw.get("masteryLevel"),
                wordType=raw.get("wordType"),
                simplified=raw.get("simplified", ""),
                traditional=raw.get("traditional", ""),
                pinyin=raw.get("pinyin", ""),
                english1=raw.get("english1", ""),
                english2=raw.get("english2", ""),
                audio_code_normal=raw.get("audio_code_normal") or raw.get("audioCodeNormal"),
                audio_code_slow=raw.get("audio_code_slow") or raw.get("audioCodeSlow"),
            )
        )
    return cards


def _write_rich_tsv(path: str, cards: Iterable[common.Flashcard]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for card in cards:
            fields = common.to_rich_fields(card, include_audio=True, audio_speed=AUDIO_SPEED)
            safe_fields = [value.replace("\t", " ") for value in fields]
            handle.write("\t".join(safe_fields))
            handle.write("\n")


def _enrich_partition(deck_root: str, partition: dict, workers: int) -> int:
    relative = partition["relative_path"].replace("/", os.sep)
    partition_dir = os.path.join(deck_root, relative)
    cards_path = os.path.join(deck_root, partition["files"]["cards_json"].replace("/", os.sep))
    media_dir = os.path.join(deck_root, partition["files"]["media_dir"].replace("/", os.sep))
    rich_path = os.path.join(partition_dir, "rich.tsv")

    cards = _load_cards(cards_path)
    common.ensure_dir(media_dir)
    jobs = common.collect_audio_jobs(cards, media_dir, AUDIO_SPEED)
    if jobs:
        print(f"Downloading audio ({len(jobs)}) for {partition['label']} → {media_dir}")
        ok, cached, failed = common.download_audio_pairs(jobs, max_workers=workers)
        print(f"  Audio summary: ok={ok} cached={cached} failed={failed}")
        if failed:
            print("  WARN: some audio files failed to download; retry if required.")
    else:
        print(f"No audio files required for {partition['label']}")

    print(f"Writing rich.tsv for {partition['label']} → {rich_path}")
    _write_rich_tsv(rich_path, cards)
    return len(cards)


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("manifest", help="Path to manifest.json produced by the extract step.")
    parser.add_argument("--audio-workers", type=int, default=8, help="Concurrent downloads for audio (default: 8).")
    return parser


def run_from_args(args: argparse.Namespace) -> None:
    manifest_path = os.path.abspath(args.manifest)
    if not os.path.exists(manifest_path):
        print(f"Error: manifest not found → {manifest_path}", file=sys.stderr)
        raise SystemExit(2)

    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    deck_root = os.path.dirname(manifest_path)
    partitions = manifest.get("partitions", [])
    if not partitions:
        print("Manifest contains no partitions; nothing to enrich.")
        return

    total_cards = 0
    for partition in partitions:
        total_cards += _enrich_partition(deck_root, partition, workers=args.audio_workers)

    print(f"Enrichment complete. Processed {total_cards} cards across {len(partitions)} partitions.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create rich.tsv files and ensure audio availability.")
    configure_parser(parser)
    args = parser.parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
