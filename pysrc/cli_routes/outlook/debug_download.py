import json
import os
import random
import subprocess
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set, Tuple

from termcolor import colored


FEATURE_ALIASES: Dict[str, str] = {
    "html": "html-body",
    "html-body": "html-body",
    "body-html": "html-body",
    "text": "text-body",
    "text-body": "text-body",
    "body-text": "text-body",
    "regular-attachments": "regular-attachments",
    "attachments": "regular-attachments",
    "inline-attachments": "inline-attachments",
    "inline": "inline-attachments",
    "item-attachments": "item-attachments",
    "items": "item-attachments",
    "link-attachments": "link-attachments",
    "links": "link-attachments",
}

FEATURE_KEYS = sorted(set(FEATURE_ALIASES.values()))

INDEX_PATH = ".dsed/debug/debug-download.json"
CACHE_ROOT = ".dsed/caches"


def _normalize_features(raw_features: Iterable[str]) -> Tuple[Optional[Set[str]], List[str]]:
    normalized: Set[str] = set()
    unknown: List[str] = []
    for raw in raw_features:
        key = raw.strip().lower()
        if not key:
            continue
        canonical = FEATURE_ALIASES.get(key)
        if not canonical:
            unknown.append(raw)
            continue
        normalized.add(canonical)
    return normalized, unknown


def _dir_has_entries(path: str, want_files: bool = False) -> bool:
    if not os.path.isdir(path):
        return False
    try:
        with os.scandir(path) as it:
            for entry in it:
                if want_files and not entry.is_file():
                    continue
                return True
    except FileNotFoundError:
        return False
    return False


def _collect_message_dirs(base_dir: str) -> List[str]:
    if not os.path.isdir(base_dir):
        return []
    message_dirs: List[str] = []
    for root, dirs, files in os.walk(base_dir):
        if "message.json" in files:
            rel = os.path.relpath(root, base_dir)
            parts = rel.split(os.sep)
            if len(parts) == 3:
                message_dirs.append(root)
                dirs[:] = []
                continue
    return message_dirs


def _features_for_message_dir(message_dir: str) -> Set[str]:
    features: Set[str] = set()

    if os.path.isfile(os.path.join(message_dir, "body.html")) or os.path.isfile(
        os.path.join(message_dir, "uniqueBody.html")
    ):
        features.add("html-body")

    if os.path.isfile(os.path.join(message_dir, "body.txt")) or os.path.isfile(
        os.path.join(message_dir, "uniqueBody.txt")
    ):
        features.add("text-body")

    attachments_root = os.path.join(message_dir, "attachments")
    if _dir_has_entries(os.path.join(attachments_root, "files"), want_files=True):
        features.add("regular-attachments")
    if _dir_has_entries(os.path.join(attachments_root, "items")):
        features.add("item-attachments")
    if _dir_has_entries(os.path.join(attachments_root, "links"), want_files=True):
        features.add("link-attachments")

    if _dir_has_entries(os.path.join(message_dir, "inline"), want_files=True):
        features.add("inline-attachments")

    return features


def _build_index(base_dir: str) -> List[Dict[str, object]]:
    message_dirs = _collect_message_dirs(base_dir)
    entries: List[Dict[str, object]] = []
    for message_dir in message_dirs:
        features = sorted(_features_for_message_dir(message_dir))
        entries.append({"path": message_dir, "features": features})
    return entries


def _write_index(entries: List[Dict[str, object]], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "messages": entries,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _load_index(path: str) -> Optional[List[Dict[str, object]]]:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    messages = data.get("messages")
    if not isinstance(messages, list):
        return None
    return messages


def impl_outlook_debug_download(raw_features: Iterable[str], build_index: bool) -> int:
    if not os.path.isdir(CACHE_ROOT):
        print(colored("Missing .dsed/caches. Run outlook download first.", "red"))
        return -1

    features, unknown = _normalize_features(raw_features)
    if unknown:
        print(colored(f"Unknown features: {', '.join(unknown)}", "red"))
        print(colored(f"Supported: {', '.join(FEATURE_KEYS)}", "yellow"))
        return -1

    if build_index:
        entries = _build_index(CACHE_ROOT)
        _write_index(entries, INDEX_PATH)
        print(colored(f"Saved debug index to {INDEX_PATH}", "green"))
        return 0

    entries = _load_index(INDEX_PATH)
    if entries is None:
        entries = _build_index(CACHE_ROOT)

    matches: List[str] = []
    for entry in entries:
        path = entry.get("path")
        entry_features = entry.get("features")
        if not isinstance(path, str):
            continue
        if not isinstance(entry_features, list):
            entry_features = []
        entry_set = {str(item) for item in entry_features}
        if features and not features.issubset(entry_set):
            continue
        matches.append(path)

    if not matches:
        print("no messages with requested features")
        return 0

    chosen = os.path.normpath(random.choice(matches))
    subprocess.Popen(["explorer", "."], cwd=chosen)
    print(chosen)
    return 0
