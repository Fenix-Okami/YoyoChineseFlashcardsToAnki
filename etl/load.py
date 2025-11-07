#!/usr/bin/env python3
"""Load step: build an Anki .apkg package from extracted data."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Iterable, List, Set, Tuple

from . import common

AUDIO_SPEED = "normal"

try:
    import genanki  # type: ignore
except Exception as exc:  # pragma: no cover - optional dependency
    genanki = None
    GENANKI_ERROR = exc
else:
    GENANKI_ERROR = None


def _require_genanki() -> None:
    if genanki is None:
        print(
            "Cannot build .apkg: genanki not installed. Install with: pip install genanki",
            file=sys.stderr,
        )
        if GENANKI_ERROR:
            print(f"Original import error: {GENANKI_ERROR}", file=sys.stderr)
        raise SystemExit(2)


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


def _read_first(paths: Iterable[str], default: str) -> str:
    for candidate in paths:
        try:
            with open(candidate, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            continue
    return default


def _build_model(script_dir: str) -> Any:
    front_html = _read_first(
        [
            os.path.join(script_dir, "anki_front_template.html"),
            os.path.join(script_dir, "tools", "anki_front_template.html"),
        ],
        "{{simplified}}",
    )
    back_html = _read_first(
        [
            os.path.join(script_dir, "anki_back_template.html"),
            os.path.join(script_dir, "tools", "anki_back_template.html"),
        ],
        "{{simplified}}<br>{{pinyin}}<br>{{english}}",
    )
    css_text = _read_first(
        [
            os.path.join(script_dir, "anki_style.css"),
            os.path.join(script_dir, "tools", "anki_style.css"),
        ],
        ".card { font-family: Georgia; font-size: 14px; }",
    )

    return genanki.Model(
        model_id=common.stable_id_from_name("YoYoChinese-Model-v2"),
        name="YoYoChinese Model",
        fields=[
            {"name": "index"},
            {"name": "simplified"},
            {"name": "traditional"},
            {"name": "pinyin"},
            {"name": "english"},
            {"name": "audio"},
            {"name": "CardType"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": front_html,
                "afmt": back_html,
            }
        ],
        css=css_text,
    )


def _notes_from_cards(
    cards: Iterable[common.Flashcard],
    model: Any,
    audio_speed: str,
    media_root: str,
    media_files: Set[str],
    seen_indexes: Set[str],
) -> List[Any]:
    notes: List["genanki.Note"] = []
    for card in cards:
        index_val = (card.code or card.id or "").strip()
        if index_val:
            if index_val in seen_indexes:
                continue
            seen_indexes.add(index_val)
        english = card.english1
        if card.english2:
            english = f"{english} | {card.english2}"
        audio_file = card.audio_filename(audio_speed)
        audio_field = ""
        if audio_file:
            media_path = os.path.join(media_root, audio_file)
            if os.path.exists(media_path):
                media_files.add(media_path)
                audio_field = f"[sound:{audio_file}]"
            else:
                print(f"  WARN: audio missing for {index_val or card.simplified}: {media_path}")
        label = common.word_type_label(card.wordType) or "Word"
        note = genanki.Note(
            model=model,
            fields=[
                index_val,
                card.simplified,
                card.traditional,
                card.pinyin,
                english,
                audio_field,
                label.lower(),
            ],
        )
        notes.append(note)
    return notes


def _build_decks_levels(
    base_name: str,
    model: Any,
    partitions: List[dict],
    deck_root: str,
    audio_speed: str,
) -> Tuple[List[Any], Set[str]]:
    decks: List["genanki.Deck"] = []
    media_files: Set[str] = set()
    seen_indexes: Set[str] = set()
    for partition in sorted(partitions, key=lambda p: (p.get("level_index") or 0, p["label"])):
        deck_name = f"{base_name}::{partition['label']}"
        deck = genanki.Deck(common.stable_id_from_name(deck_name), deck_name)
        cards = _load_cards(os.path.join(deck_root, partition["files"]["cards_json"].replace("/", os.sep)))
        media_dir = os.path.join(deck_root, partition["files"]["media_dir"].replace("/", os.sep))
        notes = _notes_from_cards(cards, model, audio_speed, media_dir, media_files, seen_indexes)
        for note in notes:
            deck.add_note(note)
        decks.append(deck)
    return decks, media_files


def _build_decks_wordtype(
    base_name: str,
    model: Any,
    partitions: List[dict],
    deck_root: str,
    audio_speed: str,
) -> Tuple[List[Any], Set[str]]:
    deck_word = genanki.Deck(common.stable_id_from_name(f"{base_name}::Word"), f"{base_name}::Word")
    deck_sentence = genanki.Deck(common.stable_id_from_name(f"{base_name}::Sentence"), f"{base_name}::Sentence")
    media_files: Set[str] = set()
    seen_indexes: Set[str] = set()

    if partitions and partitions[0]["type"] == "wordtype":
        for partition in partitions:
            cards = _load_cards(os.path.join(deck_root, partition["files"]["cards_json"].replace("/", os.sep)))
            media_dir = os.path.join(deck_root, partition["files"]["media_dir"].replace("/", os.sep))
            notes = _notes_from_cards(cards, model, audio_speed, media_dir, media_files, seen_indexes)
            target = deck_sentence if partition.get("word_type") == "Sentence" else deck_word
            for note in notes:
                target.add_note(note)
    else:
        for partition in partitions:
            cards = _load_cards(os.path.join(deck_root, partition["files"]["cards_json"].replace("/", os.sep)))
            media_dir = os.path.join(deck_root, partition["files"]["media_dir"].replace("/", os.sep))
            notes = _notes_from_cards(cards, model, audio_speed, media_dir, media_files, seen_indexes)
            for note in notes:
                label = note.fields[6]
                if label == "sentence":
                    deck_sentence.add_note(note)
                else:
                    deck_word.add_note(note)
    decks = [deck_word, deck_sentence]
    return decks, media_files


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("manifest", help="Path to manifest.json produced by the extract step.")
    parser.add_argument("--deck-name", help="Override deck name used for the package.")
    parser.add_argument("--apkg-path", help="Optional explicit path for the output .apkg file.")
    return parser


def run_from_args(args: argparse.Namespace) -> None:
    _require_genanki()

    manifest_path = os.path.abspath(args.manifest)
    if not os.path.exists(manifest_path):
        print(f"Error: manifest not found → {manifest_path}", file=sys.stderr)
        raise SystemExit(2)

    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    deck_root = os.path.dirname(manifest_path)
    deck_name = args.deck_name or manifest.get("deck_name") or "YoYoChinese"
    deck_slug = manifest.get("deck_slug") or common.slugify(deck_name)
    audio_speed = manifest.get("options", {}).get("audio_speed", AUDIO_SPEED)

    partitions = manifest.get("partitions", [])
    if not partitions:
        print("Manifest contains no partitions; nothing to load.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    model = _build_model(script_dir)

    using_levels = bool(manifest.get("options", {}).get("using_levels"))

    if using_levels:
        decks, media_files = _build_decks_levels(deck_name, model, partitions, deck_root, audio_speed)
    else:
        decks, media_files = _build_decks_wordtype(deck_name, model, partitions, deck_root, audio_speed)

    apkg_path = os.path.abspath(args.apkg_path) if args.apkg_path else os.path.join(deck_root, f"{deck_slug}.apkg")

    package = genanki.Package(decks)
    if media_files:
        package.media_files = sorted(media_files)
    package.write_to_file(apkg_path)
    print(f"Wrote Anki package → {apkg_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an Anki package from extracted YoYoChinese data.")
    configure_parser(parser)
    args = parser.parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
