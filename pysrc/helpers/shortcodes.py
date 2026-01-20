import hashlib
import json
import os
from typing import Any, Dict, Iterable, List, Tuple

SHORTCODE_PREFIX = "__"
SHORTCODE_SUFFIX = "__"
SHORTCODE_LENGTH_STEPS = [8, 12, 16, 20, 24, 32, 40, 64]


def _hash_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_shortcode_map(
    values: Iterable[str],
) -> Tuple[Dict[str, str], Dict[str, str], int]:
    ids: List[str] = []
    seen: set = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ids.append(value)

    if not ids:
        return {}, {}, 0

    digests = {value: _hash_id(value) for value in ids}
    for length in SHORTCODE_LENGTH_STEPS:
        shortcode_to_id: Dict[str, str] = {}
        collision = False
        for value in ids:
            shortcode = (
                f"{SHORTCODE_PREFIX}{digests[value][:length]}{SHORTCODE_SUFFIX}"
            )
            existing = shortcode_to_id.get(shortcode)
            if existing and existing != value:
                collision = True
                break
            shortcode_to_id[shortcode] = value
        if not collision:
            id_to_shortcode = {value: shortcode for shortcode, value in shortcode_to_id.items()}
            return id_to_shortcode, shortcode_to_id, length

    raise ValueError("Unable to build unique shortcodes with available lengths.")


def collect_folder_nodes(folder_forest: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []

    def recursion(node: Dict[str, Any]) -> None:
        nodes.append(node)
        for child in node.get("children", []):
            recursion(child)

    for root in folder_forest:
        recursion(root)

    return nodes


def apply_folder_shortcodes(
    folder_forest: List[Dict[str, Any]], id_to_shortcode: Dict[str, str]
) -> None:
    def recursion(node: Dict[str, Any]) -> None:
        folder_id = node.get("id")
        if folder_id and folder_id in id_to_shortcode:
            node["shortcode"] = id_to_shortcode[folder_id]
        for child in node.get("children", []):
            recursion(child)

    for root in folder_forest:
        recursion(root)


def write_shortcode_map(
    path: str,
    id_to_shortcode: Dict[str, str],
    shortcode_to_id: Dict[str, str],
    length: int,
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "shortcodeLength": length,
        "shortcodeToId": shortcode_to_id,
        "idToShortcode": id_to_shortcode,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
