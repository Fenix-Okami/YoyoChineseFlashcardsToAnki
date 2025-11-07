#!/usr/bin/env python3
"""Extraction step: fetch YoYoChinese flashcards and materialise raw outputs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

from . import common

AUDIO_SPEED = "normal"


@dataclass
class Partition:
    label: str
    partition_type: str  # "level", "wordtype", "all"
    relative_path: str
    cards: List[common.Flashcard]
    level_index: Optional[int] = None
    word_type: Optional[str] = None


def _prompt_for_course() -> Optional[str]:
    available = list(common.LEVEL_IDS_BY_COURSE.keys())
    if not available:
        return None
    print("Select a course to export:")
    for idx, cid in enumerate(available, start=1):
        name = common.COURSE_NAMES.get(cid, cid)
        print(f"  {idx}) {name} [{cid}]")
    choice = 1
    if sys.stdin.isatty():
        try:
            raw = input("Enter number [1]: ").strip()
            choice = int(raw) if raw else 1
        except Exception:
            choice = 1
    else:
        print("No TTY detected; defaulting to option 1.")
    if choice < 1 or choice > len(available):
        choice = 1
    return available[choice - 1]


def _write_simple_tsv(path: str, cards: List[common.Flashcard]) -> None:
    rows = [common.to_simple_fields(card) for card in cards]
    with open(path, "w", encoding="utf-8") as handle:
        for front, back in rows:
            handle.write(front.replace("\t", " "))
            handle.write("\t")
            handle.write(back.replace("\t", " "))
            handle.write("\n")


def _write_cards_json(path: str, cards: List[common.Flashcard]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump([card.to_dict() for card in cards], handle, ensure_ascii=False, indent=2)


def _download_audio(cards: List[common.Flashcard], media_dir: str, workers: int) -> None:
    jobs = common.collect_audio_jobs(cards, media_dir, AUDIO_SPEED)
    print(f"Downloading {len(jobs)} audio files → {media_dir} ...")
    ok, cached, failed = common.download_audio_pairs(jobs, max_workers=workers)
    print(f"Audio complete: ok={ok} cached={cached} failed={failed}")
    if failed:
        print("  Some audio files failed to download; rerun the step if needed.")


def _partition_cards(
    cards: List[common.Flashcard],
    using_levels: bool,
    cards_by_level: Optional[Dict[int, List[common.Flashcard]]],
    split_by_wordtype: bool,
) -> List[Partition]:
    partitions: List[Partition] = []
    if using_levels and cards_by_level:
        for lvl_idx, lvl_cards in sorted(cards_by_level.items()):
            label = f"Level {lvl_idx}"
            rel = os.path.join("levels", f"level{lvl_idx:02d}")
            partitions.append(
                Partition(
                    label=label,
                    partition_type="level",
                    relative_path=rel,
                    cards=lvl_cards,
                    level_index=lvl_idx,
                )
            )
        return partitions

    if split_by_wordtype:
        buckets: Dict[str, List[common.Flashcard]] = {"Word": [], "Sentence": [], "Other": []}
        for card in cards:
            label = common.word_type_label(card.wordType) or "Other"
            if label not in buckets:
                buckets[label] = []
            buckets[label].append(card)
        for label, bucket_cards in buckets.items():
            if not bucket_cards:
                continue
            rel = os.path.join(label.lower())
            partitions.append(
                Partition(
                    label=label,
                    partition_type="wordtype",
                    relative_path=rel,
                    cards=bucket_cards,
                    word_type=label if label in {"Word", "Sentence"} else None,
                )
            )
        return partitions

    partitions.append(
        Partition(
            label="All",
            partition_type="all",
            relative_path=os.path.join("all"),
            cards=cards,
        )
    )
    return partitions


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract YoYoChinese flashcards into TSV + audio by deck type.")
    configure_parser(parser)
    args = parser.parse_args()
    run_from_args(args)


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--cookie", help="Cookie header value for yoyochinese.com (copy from browser).")
    parser.add_argument("--deck-name", default="YoYoChinese", help="Deck name for output folders.")
    parser.add_argument("--output", default="export", help="Output directory root (default: export).")
    parser.add_argument("--per-page", type=int, default=50, help="Cards per API page (default: 50).")
    parser.add_argument("--max", dest="max_cards", type=int, help="Max cards to fetch (testing only).")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between API pages (seconds).")
    parser.add_argument("--mastery-type", default="all", help="Mastery filter (all, learning, mastered, ...).")
    parser.add_argument("--course-id", default="", help="Course ID filter (prompted when omitted).")
    parser.add_argument("--level-id", default="", help="Level ID filter.")
    parser.add_argument("--unit-id", default="", help="Unit ID filter.")
    parser.add_argument("--lesson-id", default="", help="Lesson ID filter.")
    parser.add_argument("--split-by-wordtype", action="store_true", help="Split outputs into Word/Sentence folders.")
    parser.add_argument(
        "--levels-subdecks",
        action="store_true",
        help="Fetch each configured Level separately and write Level folders (requires a mapped course).",
    )
    parser.add_argument("--audio-workers", type=int, default=8, help="Concurrent downloads for audio (default: 8).")
    return parser


def run_from_args(args: argparse.Namespace) -> None:

    cookie = args.cookie or os.getenv("YOYO_COOKIE")
    if not cookie:
        print("Error: --cookie (or env YOYO_COOKIE) is required", file=sys.stderr)
        raise SystemExit(2)

    selected_via_prompt = False
    if not args.course_id:
        selected = _prompt_for_course()
        if not selected:
            print("Error: no course-id provided and no mappings available.", file=sys.stderr)
            raise SystemExit(2)
        args.course_id = selected
        selected_via_prompt = True
        if args.deck_name.strip() == "YoYoChinese":
            args.deck_name = f"YoYoChinese {common.COURSE_NAMES.get(selected, selected)}"

    filters = {
        "masteryType": {"value": args.mastery_type, "label": args.mastery_type.capitalize()},
        "courseId": args.course_id,
        "levelId": args.level_id,
        "unitId": args.unit_id,
        "lessonId": args.lesson_id,
    }

    out_root = os.path.abspath(args.output)
    deck_slug = common.slugify(args.deck_name)
    deck_root = os.path.join(out_root, deck_slug)
    common.ensure_dir(deck_root)

    using_levels = bool(args.levels_subdecks or selected_via_prompt)
    cards: List[common.Flashcard] = []
    cards_by_level: Dict[int, List[common.Flashcard]] = {}

    if using_levels:
        if not args.course_id:
            print("Error: --levels-subdecks requires --course-id", file=sys.stderr)
            raise SystemExit(2)
        if args.course_id not in common.LEVEL_IDS_BY_COURSE:
            print("Error: course is not mapped in LEVEL_IDS_BY_COURSE.", file=sys.stderr)
            raise SystemExit(2)
        level_ids = common.LEVEL_IDS_BY_COURSE[args.course_id]
        print(f"Fetching flashcards for {len(level_ids)} levels ...")
        for idx, level_id in enumerate(level_ids, start=1):
            level_filters = dict(filters)
            level_filters.update({"levelId": level_id, "unitId": "", "lessonId": ""})
            try:
                level_cards = common.fetch_all_flashcards(
                    cookie=cookie,
                    filters=level_filters,
                    per_page=args.per_page,
                    max_cards=args.max_cards,
                    delay=args.delay,
                )
            except Exception as exc:
                print(f"Failed to fetch Level {idx}: {exc}", file=sys.stderr)
                raise SystemExit(3) from exc
            cards.extend(level_cards)
            cards_by_level[idx] = level_cards
        print(f"Fetched {sum(len(v) for v in cards_by_level.values())} cards across {len(cards_by_level)} levels.")
    else:
        try:
            cards = common.fetch_all_flashcards(
                cookie=cookie,
                filters=filters,
                per_page=args.per_page,
                max_cards=args.max_cards,
                delay=args.delay,
            )
        except Exception as exc:
            print(f"Failed to fetch flashcards: {exc}", file=sys.stderr)
            raise SystemExit(3) from exc
        print(f"Fetched {len(cards)} cards.")

    partitions = _partition_cards(cards, using_levels, cards_by_level if using_levels else None, args.split_by_wordtype)
    if not partitions:
        print("No cards returned; nothing to write.")
        return

    manifest = {
        "generated_at": common.iso_timestamp(),
        "deck_name": args.deck_name,
        "deck_slug": deck_slug,
        "course_id": args.course_id,
        "course_name": common.COURSE_NAMES.get(args.course_id),
        "filters": filters,
        "options": {
            "using_levels": using_levels,
            "split_by_wordtype": bool(args.split_by_wordtype),
            "audio_speed": AUDIO_SPEED,
        },
        "partitions": [],
    }

    for partition in partitions:
        partition_dir = os.path.join(deck_root, partition.relative_path)
        common.ensure_dir(partition_dir)
        cards_json_path = os.path.join(partition_dir, "cards.json")
        simple_tsv_path = os.path.join(partition_dir, "simple.tsv")
        media_dir = os.path.join(partition_dir, "media")
        common.ensure_dir(media_dir)

        print(f"Writing {partition.label} → {simple_tsv_path}")
        _write_simple_tsv(simple_tsv_path, partition.cards)
        _write_cards_json(cards_json_path, partition.cards)
        _download_audio(partition.cards, media_dir, workers=args.audio_workers)

        manifest["partitions"].append(
            {
                "label": partition.label,
                "type": partition.partition_type,
                "relative_path": partition.relative_path.replace("\\", "/"),
                "count": len(partition.cards),
                "level_index": partition.level_index,
                "word_type": partition.word_type,
                "files": {
                    "cards_json": os.path.relpath(cards_json_path, deck_root).replace("\\", "/"),
                    "simple_tsv": os.path.relpath(simple_tsv_path, deck_root).replace("\\", "/"),
                    "media_dir": os.path.relpath(media_dir, deck_root).replace("\\", "/"),
                },
            }
        )

    manifest_path = os.path.join(deck_root, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    print(f"Wrote manifest → {manifest_path}")
    print("Extraction complete.")


if __name__ == "__main__":
    main()
