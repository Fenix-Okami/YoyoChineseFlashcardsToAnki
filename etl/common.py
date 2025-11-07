#!/usr/bin/env python3
"""Shared helpers for the YoYoChinese → Anki ETL pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import urllib.error
    import urllib.request
except Exception as exc:  # pragma: no cover - should never happen in stdlib
    raise SystemExit(f"Failed to import urllib: {exc}")

API_URL = "https://yoyochinese.com/api/v1/flashcards/manage/cards"
CDN_AUDIO_BASE = "https://cdn.yoyochinese.com/audio/practice/"

LEVEL_IDS_BY_COURSE: Dict[str, List[str]] = {
    "5f9c5382c32d410f1447bee9": [
        "5f9c5382c32d410f1447bef5",
        "5f9c5382c32d410f1447bef6",
        "5f9c5382c32d410f1447bef7",
        "5f9c5382c32d410f1447bef8",
        "5f9c5382c32d410f1447bef9",
        "5f9c5382c32d410f1447befa",
    ],
    "5f9c5382c32d410f1447beeb": [
        "5f9c5382c32d410f1447bf01",
        "5f9c5382c32d410f1447bf02",
        "5f9c5382c32d410f1447bf03",
        "5f9c5382c32d410f1447bf04",
        "5f9c5382c32d410f1447bf05",
        "5f9c5382c32d410f1447bf06",
    ],
    "5f9c5382c32d410f1447beea": [
        "5f9c5382c32d410f1447befb",
        "5f9c5382c32d410f1447befc",
        "5f9c5382c32d410f1447befd",
        "5f9c5382c32d410f1447befe",
        "5f9c5382c32d410f1447beff",
        "5f9c5382c32d410f1447bf00",
    ],
    "5f9c5382c32d410f1447beed": [
        "5f9c5382c32d410f1447bf0d",
        "5f9c5382c32d410f1447bf0e",
        "5f9c5382c32d410f1447bf0f",
        "5f9c5382c32d410f1447bf10",
        "5f9c5382c32d410f1447bf11",
        "5f9c5382c32d410f1447bf12",
    ],
    "5f9c5382c32d410f1447beec": [
        "5f9c5382c32d410f1447bf07",
        "5f9c5382c32d410f1447bf08",
        "5f9c5382c32d410f1447bf09",
        "5f9c5382c32d410f1447bf0a",
        "5f9c5382c32d410f1447bf0b",
        "5f9c5382c32d410f1447bf0c",
    ],
    "5f9c5382c32d410f1447beee": [
        "5f9c5382c32d410f1447bf13",
        "5f9c5382c32d410f1447bf14",
        "5f9c5382c32d410f1447bf15",
        "5f9c5382c32d410f1447bf16",
        "5f9c5382c32d410f1447bf17",
        "5f9c5382c32d410f1447bf18",
    ],
}

COURSE_NAMES: Dict[str, str] = {
    "5f9c5382c32d410f1447bee9": "Beginner Conversational",
    "5f9c5382c32d410f1447beeb": "Chinese Characters",
    "5f9c5382c32d410f1447beea": "Intermediate Conversational",
    "5f9c5382c32d410f1447beed": "Chinese Characters II",
    "5f9c5382c32d410f1447beec": "Upper Intermediate Conversational",
    "5f9c5382c32d410f1447beee": "Chinese Character Reader",
}


@dataclass
class Flashcard:
    id: str
    code: str
    masteryLevel: Optional[int]
    wordType: Optional[int]
    simplified: str
    traditional: str
    pinyin: str
    english1: str
    english2: str
    audio_code_normal: Optional[str]
    audio_code_slow: Optional[str]

    @staticmethod
    def from_api(obj: Dict) -> "Flashcard":
        content = obj.get("content", {})
        return Flashcard(
            id=str(obj.get("id") or obj.get("_id") or ""),
            code=obj.get("code") or "",
            masteryLevel=obj.get("masteryLevel"),
            wordType=obj.get("wordType"),
            simplified=(content.get("simplified") or "").strip(),
            traditional=(content.get("traditional") or "").strip(),
            pinyin=(content.get("pinyin") or "").strip(),
            english1=(content.get("english1") or "").strip(),
            english2=(content.get("english2") or "").strip(),
            audio_code_normal=content.get("normal"),
            audio_code_slow=content.get("slow"),
        )

    def audio_filename(self, speed: str = "normal") -> Optional[str]:
        if speed == "normal":
            code = self.audio_code_normal
        elif speed == "slow":
            code = self.audio_code_slow
        else:
            code = None
        if not code:
            return None
        return f"{code}.mp3"

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["audio_normal"] = self.audio_filename("normal")
        data["audio_slow"] = self.audio_filename("slow")
        return data


def build_headers(cookie: Optional[str]) -> Dict[str, str]:
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "is-native": "false",
    }
    if not cookie:
        return headers
    value = cookie.strip()
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()
    headers["Cookie"] = value
    return headers


def http_post_json(url: str, body: Dict, headers: Dict[str, str], timeout: int = 30) -> Dict:
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            text = resp.read().decode(charset, errors="replace")
            return json.loads(text)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        raise RuntimeError(f"HTTP {exc.code} error: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc


def http_download(
    url: str,
    dest_path: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    retries: int = 4,
    backoff: float = 0.75,
) -> None:
    req = urllib.request.Request(url, method="GET")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    if not headers or "range" not in headers:
        req.add_header("range", "bytes=0-")

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tmp_path = dest_path + ".part"

    last_error: Optional[Exception] = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp_path, "wb") as handle:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    handle.write(chunk)
            os.replace(tmp_path, dest_path)
            return
        except Exception as exc:  # noqa: PIE786 - broad for retry loop
            last_error = exc
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            if attempt >= retries:
                break
            sleep_s = backoff * (2 ** (attempt - 1)) + min(0.25, 0.05 * attempt)
            time.sleep(sleep_s)
    raise RuntimeError(f"download failed after {retries} attempts: {last_error}")


def fetch_all_flashcards(
    cookie: Optional[str],
    filters: Dict,
    per_page: int,
    max_cards: Optional[int],
    delay: float,
) -> List[Flashcard]:
    headers = build_headers(cookie)
    page = 1
    cards: List[Flashcard] = []
    total: Optional[int] = None

    while True:
        body = {"filters": filters, "page": page, "cardsPerPage": per_page}
        data = http_post_json(API_URL, body, headers)
        batch = [Flashcard.from_api(item) for item in data.get("flashcards", [])]
        cards.extend(batch)
        total = data.get("totalFlashcards") if total is None else total
        print(
            f"Fetched page {page}, +{len(batch)} cards (total so far: {len(cards)} / {total or '?'})"
        )
        if max_cards is not None and len(cards) >= max_cards:
            return cards[:max_cards]
        if not batch:
            return cards
        if total is not None and len(cards) >= total:
            return cards
        page += 1
        if delay > 0:
            time.sleep(delay)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def slugify(value: str) -> str:
    cleaned = re.sub(r"\s+", "_", value.strip())
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", cleaned)
    cleaned = cleaned.strip("._-")
    return cleaned or "deck"


def word_type_label(word_type: Optional[int]) -> str:
    if word_type == 2:
        return "Word"
    if word_type == 3:
        return "Sentence"
    return ""


def to_simple_fields(card: Flashcard) -> Tuple[str, str]:
    english = card.english1
    if card.english2:
        english = f"{english} | {card.english2}"
    back = f"{card.pinyin} — {english}" if card.pinyin else english
    return card.simplified, back


def to_rich_fields(card: Flashcard, include_audio: bool, audio_speed: str = "normal") -> List[str]:
    english = card.english1
    if card.english2:
        english = f"{english} | {card.english2}"
    audio_file = card.audio_filename(audio_speed) if include_audio else None
    audio_field = f"[sound:{audio_file}]" if audio_file else ""
    return [
        card.simplified,
        card.pinyin,
        english,
        card.traditional,
        audio_field,
        card.code,
        word_type_label(card.wordType),
    ]


def collect_audio_jobs(cards: Sequence[Flashcard], dest_dir: str, audio_speed: str) -> List[Tuple[str, str]]:
    jobs: List[Tuple[str, str]] = []
    for card in cards:
        filename = card.audio_filename(audio_speed)
        if not filename:
            continue
        url = CDN_AUDIO_BASE + filename
        jobs.append((url, os.path.join(dest_dir, filename)))
    # Preserve first occurrence order, deduplicate duplicates
    distinct: Dict[Tuple[str, str], None] = {}
    for pair in jobs:
        distinct.setdefault(pair, None)
    return list(distinct.keys())


def download_audio_pairs(
    pairs: Sequence[Tuple[str, str]],
    max_workers: int = 8,
) -> Tuple[int, int, int]:
    if not pairs:
        return (0, 0, 0)
    ok = 0
    cached = 0
    failed = 0
    total = len(pairs)
    lock = threading.Lock()

    def worker(pair: Tuple[str, str]) -> Tuple[str, Tuple[str, str], Optional[str]]:
        url, dest = pair
        try:
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                return ("cached", pair, None)
            http_download(url, dest)
            return ("downloaded", pair, None)
        except Exception as exc:  # noqa: PIE786 - broad for download retries
            return ("failed", pair, str(exc))

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = [executor.submit(worker, pair) for pair in pairs]
        for idx, fut in enumerate(as_completed(futures), start=1):
            status, pair, err = fut.result()
            with lock:
                if status == "downloaded":
                    ok += 1
                elif status == "cached":
                    ok += 1
                    cached += 1
                else:
                    failed += 1
                    url, _ = pair
                    print(f"  WARN: failed {url} → {err}")
                if idx % 25 == 0 or idx == total:
                    print(f"  [{idx}/{total}] ok={ok} cached={cached} failed={failed}")
    return ok, cached, failed


def stable_id_from_name(name: str) -> int:
    return int(hashlib.md5(name.encode("utf-8")).hexdigest()[:8], 16)


def iso_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
