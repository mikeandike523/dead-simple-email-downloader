import json
import os
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from termcolor import colored

from pysrc.call_route import call_route


WIN_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
}

DEFAULT_NAME = "INVALID_FILENAME"


def _utf8_percent_encode(ch: str) -> str:
    return "".join(f"%{b:02X}" for b in ch.encode("utf-8"))


def _safe_filename(input_name: Optional[str]) -> str:
    name = unicodedata.normalize("NFC", (input_name or "")).strip()
    if not name or re.fullmatch(r"[\x00-\x1F\x7F]+", name):
        name = DEFAULT_NAME

    if name in {".", ".."}:
        name = f"_{name}"

    raw_base = name.split(".")[0].lower()
    if raw_base in WIN_RESERVED:
        name = f"_{name}"

    while name and name[-1] in {" ", "."}:
        name = name[:-1] + "_"

    if not name:
        name = DEFAULT_NAME

    encoded = []
    for ch in name:
        code = ord(ch)
        if code <= 0x1F or code == 0x7F:
            encoded.append(_utf8_percent_encode(ch))
            continue
        if ch == "/":
            encoded.append("%2F")
            continue
        if re.search(r'[<>:"/\\|?*]', ch):
            encoded.append(_utf8_percent_encode(ch))
            continue
        encoded.append(ch)

    result = "".join(encoded)
    return result or DEFAULT_NAME


def _truncate_subject(value: str, limit: int = 36) -> str:
    if len(value) <= limit:
        return value
    trimmed = value[:limit]
    if trimmed.endswith("%"):
        trimmed = trimmed[:-1]
    elif len(trimmed) >= 2 and trimmed[-2] == "%":
        trimmed = trimmed[:-2]
    removed = len(value) - len(trimmed)
    if removed <= 0:
        return trimmed
    return f"{trimmed}...({removed} more)"


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    s = dt_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(s)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _message_datetime(meta: Dict[str, Any]) -> datetime:
    dt = _parse_iso_datetime(meta.get("receivedDateTime")) or _parse_iso_datetime(
        meta.get("sentDateTime")
    )
    if dt:
        return dt
    epoch = meta.get("receivedEpoch") or meta.get("sentEpoch")
    if isinstance(epoch, (int, float)):
        return datetime.fromtimestamp(epoch / 1000, tz=timezone.utc)
    return datetime.fromtimestamp(0, tz=timezone.utc)


def _format_datetime_label(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def _order_prefix(index: int, total: int, min_digits: int = 2) -> str:
    digits = max(min_digits, len(str(max(total, 1))))
    return f"__{index:0{digits}d}__"


def _to_windows_path(path: str) -> Optional[str]:
    if path.startswith("/mnt/") and len(path) > 6:
        drive = path[5].upper()
        rest = path[6:].lstrip("/")
        win_sep = "\\"
        return f"{drive}:\\" + rest.replace("/", win_sep)
    return None


def _set_folder_times(path: str, dt: datetime) -> None:
    ts = dt.timestamp()
    try:
        os.utime(path, (ts, ts))
    except Exception:
        pass

    win_path = _to_windows_path(path)
    if not win_path:
        return
    ps = shutil.which("powershell.exe")
    if not ps:
        return
    dt_iso = dt.isoformat()
    cmd = (
        f"$dt = [datetime]::Parse('{dt_iso}'); "
        f"$item = Get-Item -LiteralPath '{win_path}'; "
        "$item.CreationTime = $dt; "
        "$item.LastWriteTime = $dt"
    )
    try:
        subprocess.run([ps, "-NoProfile", "-Command", cmd], check=False)
    except Exception:
        pass


def _load_folder_forest() -> Optional[List[Dict[str, Any]]]:
    if not os.path.isfile(".dsed/index/folders.json"):
        print(colored("Missing .dsed/index/folders.json. Run outlook index first.", "red"))
        return None
    with open(".dsed/index/folders.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _folder_display_path(node_names: Iterable[str]) -> str:
    return " -> ".join(node_names)


def _collect_folders_in_order(
    forest: List[Dict[str, Any]],
) -> List[Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
    collected: List[Tuple[List[Dict[str, Any]], Dict[str, Any]]] = []

    def recursion(node: Dict[str, Any], prior: List[Dict[str, Any]]) -> None:
        collected.append((prior, node))
        for child in node.get("children", []):
            recursion(child, prior + [node])

    for root in forest:
        recursion(root, [])
    return collected


def _build_folder_segment(node: Dict[str, Any]) -> str:
    shortcode = node.get("shortcode") or "__missing__"
    safe_name = node.get("safeFilename") or _safe_filename(node.get("name"))
    return f"{shortcode}__{safe_name}"


def _load_folder_conversations(folder_shortcode: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(".dsed/index/conversations-organized", f"{folder_shortcode}.json")
    if not os.path.isfile(path):
        print(
            colored(
                f"Missing conversation index for folder shortcode {folder_shortcode}. Run outlook index first.",
                "red",
            )
        )
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _copy_message_cache(cache_dir: str, output_dir: str) -> bool:
    if not os.path.isdir(cache_dir):
        return False
    shutil.copytree(cache_dir, output_dir, dirs_exist_ok=True)
    return True


def export_outlook_output(outdir: str, max_subject_chars: int = 36) -> int:
    forest = _load_folder_forest()
    if forest is None:
        return -1

    if not os.path.isdir(".dsed/caches"):
        print(colored("Missing .dsed/caches. Run outlook download first.", "red"))
        return -1

    _ensure_dir(outdir)

    folder_shortcodes = None
    if os.path.isfile(".dsed/index/shortcodes/folders.json"):
        with open(".dsed/index/shortcodes/folders.json", "r", encoding="utf-8") as f:
            folder_shortcodes = json.load(f)

    user_data = None
    resp = call_route("/outlook/me", "Fetching user info for output...")
    if resp is not None:
        user_data = resp.data
        if isinstance(user_data, dict) and "graphAccessToken" in user_data:
            user_data = dict(user_data)

    me_payload = {
        "generatedAtUtc": datetime.now(tz=timezone.utc).isoformat(),
        "user": user_data,
        "folders": forest,
        "folderShortcodes": folder_shortcodes,
        "source": {
            "indexPath": ".dsed/index",
            "cachePath": ".dsed/caches",
        },
    }
    _write_json(os.path.join(outdir, "me.json"), me_payload)

    folders = _collect_folders_in_order(forest)
    for parents, node in folders:
        folder_id = node.get("id")
        folder_shortcode = node.get("shortcode")
        if not folder_id or not folder_shortcode:
            print(colored("Missing folder id or shortcode during output.", "red"))
            return -1

        parent_segments = [_build_folder_segment(p) for p in parents]
        folder_segment = _build_folder_segment(node)
        folder_out_dir = os.path.join(outdir, *parent_segments, folder_segment)
        _ensure_dir(folder_out_dir)

        parent_names = [p.get("name", "") for p in parents]
        display_path = _folder_display_path(parent_names + [node.get("name", "")])

        conversations_data = _load_folder_conversations(folder_shortcode)
        if conversations_data is None:
            return -1
        conversations = conversations_data.get("conversations", [])

        folder_index_payload = {
            "folderId": folder_id,
            "folderShortcode": folder_shortcode,
            "name": node.get("name"),
            "safeFilename": node.get("safeFilename"),
            "displayPath": display_path,
            "conversationShortcodes": conversations_data.get("conversationShortcodes"),
            "conversationShortcodeLength": conversations_data.get(
                "conversationShortcodeLength"
            ),
            "outputFolder": os.path.relpath(folder_out_dir, outdir),
            "cacheFolder": os.path.relpath(
                os.path.join(".dsed/caches", folder_shortcode), "."
            ),
            "conversations": [
                {
                    "conversationId": c.get("conversationId"),
                    "conversationShortcode": c.get("conversationShortcode"),
                    "messageShortcodes": c.get("messageShortcodes"),
                    "messageShortcodeLength": c.get("messageShortcodeLength"),
                    "messages": c.get("messages"),
                }
                for c in conversations
                if isinstance(c, dict)
            ],
        }
        _write_json(os.path.join(folder_out_dir, "folder_index.json"), folder_index_payload)

        folder_cache_dir = os.path.join(".dsed/caches", folder_shortcode)
        total_conversations = len(conversations)
        for conv_index, conversation in enumerate(conversations, start=1):
            if not isinstance(conversation, dict):
                continue
            conversation_id = conversation.get("conversationId")
            conversation_shortcode = conversation.get("conversationShortcode")
            messages = conversation.get("messages", [])
            if not conversation_id or not conversation_shortcode or not isinstance(messages, list):
                continue

            first_meta = messages[0] if messages else {}
            conv_dt = _message_datetime(first_meta if isinstance(first_meta, dict) else {})
            conv_subject_raw = (
                first_meta.get("subject") if isinstance(first_meta, dict) else None
            )
            conv_subject = _truncate_subject(
                _safe_filename(conv_subject_raw or "no_subject"),
                limit=max_subject_chars,
            )
            conv_label = _format_datetime_label(conv_dt)
            conv_prefix = _order_prefix(conv_index, total_conversations)
            conv_dir_name = (
                f"{conv_prefix}{conversation_shortcode}__{conv_label}__{conv_subject}"
            )
            conv_out_dir = os.path.join(folder_out_dir, conv_dir_name)
            _ensure_dir(conv_out_dir)
            _set_folder_times(conv_out_dir, conv_dt)

            conv_cache_dir = os.path.join(folder_cache_dir, conversation_shortcode)
            conv_index_payload = {
                "folderId": folder_id,
                "folderShortcode": folder_shortcode,
                "conversationId": conversation_id,
                "conversationShortcode": conversation_shortcode,
                "conversationDateUtc": conv_dt.isoformat(),
                "conversationSubject": conv_subject_raw,
                "messageShortcodes": conversation.get("messageShortcodes"),
                "messageShortcodeLength": conversation.get("messageShortcodeLength"),
                "outputFolder": os.path.relpath(conv_out_dir, outdir),
                "cacheFolder": os.path.relpath(conv_cache_dir, "."),
                "messages": [],
            }

            total_messages = len(messages)
            for msg_index, message_meta in enumerate(messages, start=1):
                if not isinstance(message_meta, dict):
                    continue
                message_id = message_meta.get("id")
                message_shortcode = message_meta.get("shortcode")
                if not message_id or not message_shortcode:
                    continue

                msg_dt = _message_datetime(message_meta)
                msg_subject_raw = message_meta.get("subject") or "no_subject"
                msg_subject = _truncate_subject(
                    _safe_filename(msg_subject_raw),
                    limit=max_subject_chars,
                )
                msg_label = _format_datetime_label(msg_dt)
                msg_prefix = _order_prefix(msg_index, total_messages)
                msg_dir_name = (
                    f"{msg_prefix}{message_shortcode}__{msg_label}__{msg_subject}"
                )
                msg_out_dir = os.path.join(conv_out_dir, msg_dir_name)

                cache_dir = os.path.join(conv_cache_dir, message_shortcode)
                if not _copy_message_cache(cache_dir, msg_out_dir):
                    print(
                        colored(
                            f"Missing cache for message {message_id} ({message_shortcode}).",
                            "red",
                        )
                    )
                    return -1

                msg_index_payload = {
                    "folderId": folder_id,
                    "folderShortcode": folder_shortcode,
                    "conversationId": conversation_id,
                    "conversationShortcode": conversation_shortcode,
                    "messageId": message_id,
                    "messageShortcode": message_shortcode,
                    "receivedDateTime": message_meta.get("receivedDateTime"),
                    "sentDateTime": message_meta.get("sentDateTime"),
                    "subject": message_meta.get("subject"),
                    "cacheRelativePath": os.path.relpath(cache_dir, "."),
                    "outputFolder": os.path.relpath(msg_out_dir, outdir),
                }
                _write_json(os.path.join(msg_out_dir, "message_index.json"), msg_index_payload)

                conv_index_payload["messages"].append(
                    {
                        "messageId": message_id,
                        "messageShortcode": message_shortcode,
                        "messageMeta": dict(message_meta),
                        "outputFolder": os.path.relpath(msg_out_dir, outdir),
                    }
                )

                _set_folder_times(msg_out_dir, msg_dt)

            _write_json(
                os.path.join(conv_out_dir, "conversation_index.json"),
                conv_index_payload,
            )

    print(colored("Output export complete.", "green"))
    return 0
