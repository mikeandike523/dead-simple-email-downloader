import base64
import json
import mimetypes
import os
import shutil
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from termcolor import colored
from tqdm import tqdm

from pysrc.call_route import BASE_URL, _load_jwt
from pysrc.utils.summarize_response import summarize_response


def _api_request_json(
    route: str,
    params: Optional[Dict[str, Any]] = None,
    method: str = "GET",
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Optional[Any]:
    jwt = _load_jwt()
    if not jwt:
        return None
    url = f"{BASE_URL.rstrip('/')}/api/{route.lstrip('/')}"
    headers = {"Authorization": f"Bearer {jwt}"}
    resp = requests.request(
        method,
        url,
        headers=headers,
        params=params or None,
        json=json_body,
        timeout=timeout,
    )
    summary = summarize_response(resp)
    if not summary.ok:
        print(colored(f"Request failed: {route} ({summary.status})", "red"))
        if summary.text:
            print(summary.text)
        return None
    return summary.data


def _api_request_binary(
    route: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Optional[Tuple[bytes, str]]:
    jwt = _load_jwt()
    if not jwt:
        return None
    url = f"{BASE_URL.rstrip('/')}/api/{route.lstrip('/')}"
    headers = {"Authorization": f"Bearer {jwt}"}
    resp = requests.get(url, headers=headers, params=params or None, timeout=timeout)
    if not resp.ok:
        print(
            colored(
                f"Binary request failed: {route} ({resp.status_code})", "red"
            )
        )
        return None
    content_type = resp.headers.get("Content-Type", "application/octet-stream")
    return resp.content, content_type


def _sanitize_filename(name: Optional[str], content_type: Optional[str]) -> str:
    raw = (name or "").strip()
    if not raw:
        raw = "attachment"

    base, ext = os.path.splitext(raw)
    base = base.strip() or "attachment"

    guessed_ext = mimetypes.guess_extension(content_type or "") if content_type else None
    if not ext and guessed_ext:
        ext = guessed_ext
    if not ext:
        ext = ".bin"

    ext = ext.lower()
    if not ext.startswith("."):
        ext = "." + ext

    base = base.lower()
    base = re.sub(r"\s+", "_", base)
    base = re.sub(r"[^a-z0-9._-]", "_", base)
    base = re.sub(r"_+", "_", base).strip("._-")
    if not base:
        base = "attachment"

    return f"{base}{ext}"


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _write_text(path: str, data: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)


def _write_binary(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


def _normalize_cid(cid: Optional[str]) -> Optional[str]:
    if not cid:
        return None
    cid = cid.strip()
    if cid.startswith("<") and cid.endswith(">"):
        cid = cid[1:-1]
    return cid


def _rewrite_inline_html(
    html: str,
    cid_map: Dict[str, str],
    location_map: Dict[str, str],
) -> Tuple[str, bool]:
    rewritten = html
    for cid, rel_path in cid_map.items():
        if not cid:
            continue
        rewritten = rewritten.replace(f"cid:{cid}", rel_path)
        rewritten = rewritten.replace(f"cid:<{cid}>", rel_path)
    for loc, rel_path in location_map.items():
        if not loc:
            continue
        rewritten = rewritten.replace(loc, rel_path)
    return rewritten, rewritten != html


def _get_message(message_id: str) -> Optional[Dict[str, Any]]:
    return _api_request_json(
        "/outlook/download/get-message", params={"messageId": message_id}
    )


def _get_attachments(message_id: str) -> Optional[List[Dict[str, Any]]]:
    data = _api_request_json(
        "/outlook/download/get-attachments", params={"messageId": message_id}
    )
    if isinstance(data, dict) and isinstance(data.get("attachments"), list):
        return data["attachments"]
    return None


def _get_attachment_with_item(
    message_id: str, attachment_id: str
) -> Optional[Dict[str, Any]]:
    return _api_request_json(
        "/outlook/download/get-attachment",
        params={"messageId": message_id, "attachmentId": attachment_id},
    )


def _get_attachment_value(
    message_id: str, attachment_id: str
) -> Optional[Tuple[bytes, str]]:
    return _api_request_binary(
        "/outlook/download/get-attachment-value",
        params={"messageId": message_id, "attachmentId": attachment_id},
    )


def _get_item_value(item_type: str, item_id: str) -> Optional[Tuple[bytes, str]]:
    return _api_request_binary(
        "/outlook/download/get-item-value",
        params={"itemType": item_type, "itemId": item_id},
    )


def _export_body_files(
    body_obj: Optional[Dict[str, Any]],
    message_dir: str,
    basename: str,
    inline_maps: Optional[Tuple[Dict[str, str], Dict[str, str]]] = None,
) -> None:
    if not body_obj or "contentType" not in body_obj:
        return

    content_type = body_obj.get("contentType")
    content = body_obj.get("content")
    if content is None:
        return

    ext = "html" if content_type == "html" else "txt"
    target_path = os.path.join(message_dir, f"{basename}.{ext}")
    original_content = content

    if inline_maps and content_type == "html":
        cid_map, location_map = inline_maps
        rewritten, changed = _rewrite_inline_html(content, cid_map, location_map)
        if changed:
            no_parse_path = os.path.join(message_dir, f"{basename}_noParse.html")
            _write_text(no_parse_path, original_content)
            content = rewritten

    _write_text(target_path, content)


def _message_for_json(message: Dict[str, Any]) -> Dict[str, Any]:
    message_json = dict(message)
    for key in ("body", "uniqueBody"):
        body_obj = message.get(key)
        if isinstance(body_obj, dict) and "contentType" in body_obj:
            message_json[key] = {"contentType": body_obj.get("contentType")}
        else:
            message_json[key] = None
    return message_json


def _export_event_item(item: Dict[str, Any], base_dir: str) -> None:
    _write_json(os.path.join(base_dir, "event.json"), item)
    item_id = item.get("id")
    if item_id:
        value = _get_item_value("event", item_id)
        if value:
            data, _content_type = value
            _write_binary(os.path.join(base_dir, "event.ics"), data)


def _export_contact_item(item: Dict[str, Any], base_dir: str) -> None:
    _write_json(os.path.join(base_dir, "contact.json"), item)
    item_id = item.get("id")
    if item_id:
        value = _get_item_value("contact", item_id)
        if value:
            data, _content_type = value
            _write_binary(os.path.join(base_dir, "contact.vcf"), data)


def _export_message_from_data(
    message: Dict[str, Any],
    message_dir: str,
    message_id: Optional[str],
    allow_graph_attachments: bool,
) -> None:
    _ensure_dir(message_dir)
    attachments_dir = os.path.join(message_dir, "attachments")
    attachments_files_dir = os.path.join(attachments_dir, "files")
    attachments_links_dir = os.path.join(attachments_dir, "links")
    attachments_items_dir = os.path.join(attachments_dir, "items")
    inline_dir = os.path.join(message_dir, "inline")

    _ensure_dir(attachments_files_dir)
    _ensure_dir(attachments_links_dir)
    _ensure_dir(attachments_items_dir)
    _ensure_dir(inline_dir)

    _write_json(os.path.join(message_dir, "message.json"), _message_for_json(message))

    inline_cid_map: Dict[str, str] = {}
    inline_location_map: Dict[str, str] = {}
    files_map: List[Dict[str, Any]] = []

    attachments: List[Dict[str, Any]] = []
    if allow_graph_attachments and message_id:
        fetched = _get_attachments(message_id)
        if fetched is not None:
            attachments = fetched
    if not attachments and isinstance(message.get("attachments"), list):
        attachments = message["attachments"]

    _write_json(os.path.join(message_dir, "attachments.json"), attachments)

    for att in attachments:
        attachment_id = att.get("id")
        odata_type = att.get("@odata.type") or att.get("odataType")
        is_inline = bool(att.get("isInline"))
        original_name = att.get("name")
        content_type = att.get("contentType")
        size = att.get("size")
        content_id = _normalize_cid(att.get("contentId"))
        content_location = att.get("contentLocation")

        attachment_type = "unknown"
        if isinstance(odata_type, str):
            if "fileAttachment" in odata_type:
                attachment_type = "fileAttachment"
            elif "referenceAttachment" in odata_type:
                attachment_type = "referenceAttachment"
            elif "itemAttachment" in odata_type:
                attachment_type = "itemAttachment"

        sanitized_name = _sanitize_filename(original_name, content_type)

        if attachment_type == "referenceAttachment":
            if attachment_id:
                _write_json(
                    os.path.join(attachments_links_dir, f"{attachment_id}.json"), att
                )
            files_map.append(
                {
                    "attachmentId": attachment_id,
                    "attachmentType": attachment_type,
                    "isInline": is_inline,
                    "originalName": original_name,
                    "sanitizedName": sanitized_name,
                    "relativePath": None,
                    "contentType": content_type,
                    "size": size,
                    "contentId": content_id,
                    "contentLocation": content_location,
                }
            )
            continue

        if attachment_type == "fileAttachment":
            if not attachment_id:
                continue
            filename = f"{attachment_id}__{sanitized_name}"
            if is_inline:
                rel_path = f"inline/{filename}"
                disk_path = os.path.join(inline_dir, filename)
            else:
                rel_path = f"attachments/files/{filename}"
                disk_path = os.path.join(attachments_files_dir, filename)

            blob: Optional[Tuple[bytes, str]] = None
            if att.get("contentBytes"):
                try:
                    blob = (base64.b64decode(att["contentBytes"]), content_type or "")
                except Exception:
                    blob = None
            if blob is None and message_id:
                blob = _get_attachment_value(message_id, attachment_id)
            if blob:
                data, _ct = blob
                _write_binary(disk_path, data)

            if is_inline:
                if content_id:
                    inline_cid_map[content_id] = rel_path
                if content_location:
                    inline_location_map[content_location] = rel_path

            files_map.append(
                {
                    "attachmentId": attachment_id,
                    "attachmentType": attachment_type,
                    "isInline": is_inline,
                    "originalName": original_name,
                    "sanitizedName": sanitized_name,
                    "relativePath": rel_path,
                    "contentType": content_type,
                    "size": size,
                    "contentId": content_id,
                    "contentLocation": content_location,
                }
            )
            continue

        if attachment_type == "itemAttachment":
            if not attachment_id:
                continue
            item_dir = os.path.join(attachments_items_dir, attachment_id)
            _ensure_dir(item_dir)
            detail = None
            if message_id:
                detail = _get_attachment_with_item(message_id, attachment_id)
            if detail is None:
                detail = att
            _write_json(os.path.join(item_dir, "attachment.json"), detail)

            item = None
            if isinstance(detail, dict):
                item = detail.get("item") if isinstance(detail.get("item"), dict) else None

            if item:
                item_type = item.get("@odata.type", "")
                if "message" in item_type:
                    _export_message_from_data(
                        item,
                        item_dir,
                        item.get("id"),
                        allow_graph_attachments=True,
                    )
                elif "event" in item_type:
                    _export_event_item(item, item_dir)
                elif "contact" in item_type:
                    _export_contact_item(item, item_dir)
                else:
                    _write_json(os.path.join(item_dir, "item.json"), item)

            files_map.append(
                {
                    "attachmentId": attachment_id,
                    "attachmentType": attachment_type,
                    "isInline": is_inline,
                    "originalName": original_name,
                    "sanitizedName": sanitized_name,
                    "relativePath": f"attachments/items/{attachment_id}",
                    "contentType": content_type,
                    "size": size,
                    "contentId": content_id,
                    "contentLocation": content_location,
                }
            )
            continue

    _write_json(os.path.join(message_dir, "files_map.json"), files_map)

    inline_maps = (inline_cid_map, inline_location_map)
    _export_body_files(message.get("body"), message_dir, "body", inline_maps)
    _export_body_files(message.get("uniqueBody"), message_dir, "uniqueBody", inline_maps)


def _export_message_by_id(message_id: str, message_dir: str) -> bool:
    message = _get_message(message_id)
    if message is None:
        return False
    _export_message_from_data(message, message_dir, message_id, True)
    return True


def _load_folder_forest() -> Optional[List[Dict[str, Any]]]:
    if not os.path.isfile(".dsed/index/folders.json"):
        print(colored("Missing .dsed/index/folders.json. Run indexing first.", "red"))
        return None
    with open(".dsed/index/folders.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _collect_folders_in_order(
    forest: List[Dict[str, Any]],
) -> List[Tuple[str, Dict[str, Any]]]:
    folders: List[Tuple[str, Dict[str, Any]]] = []

    def recursion(node: Dict[str, Any], prior: Tuple[str, ...]) -> None:
        folders.append(("\u2192".join(prior + (node["name"],)), node))
        for child in node.get("children", []):
            recursion(child, prior + (node["name"],))

    for root in forest:
        recursion(root, tuple())
    return folders


def _load_conversations(folder_id: str) -> Optional[List[Dict[str, Any]]]:
    path = f".dsed/index/conversations-organized/{folder_id}.json"
    if not os.path.isfile(path):
        print(
            colored(
                f"Missing conversation index for folder {folder_id}. Run indexing first.",
                "red",
            )
        )
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def download_all_folders(reset: bool = False) -> int:
    if reset:
        if os.path.isdir(".dsed/caches"):
            shutil.rmtree(".dsed/caches")
        os.makedirs(".dsed/caches")
        return 0

    forest = _load_folder_forest()
    if forest is None:
        return -1

    folders = _collect_folders_in_order(forest)
    if not folders:
        print(colored("No folders found.", "red"))
        return -1

    os.makedirs(".dsed/caches", exist_ok=True)

    for i, (folder_name, node) in enumerate(folders):
        folder_id = node["id"]
        conversations = _load_conversations(folder_id)
        if conversations is None:
            return -1

        folder_cache_dir = os.path.join(".dsed/caches", folder_id)
        _ensure_dir(folder_cache_dir)

        total_items = sum(len(c.get("messages", [])) for c in conversations)
        desc = f"Processing folder {folder_name} (folder {i+1}/{len(folders)})."
        with tqdm(total=total_items, desc=desc) as pbar:
            for conversation in conversations:
                conversation_id = conversation.get("conversationId")
                if not conversation_id:
                    continue
                conv_dir = os.path.join(folder_cache_dir, conversation_id)
                _ensure_dir(conv_dir)

                for message_meta in conversation.get("messages", []):
                    message_id = message_meta.get("id")
                    if not message_id:
                        pbar.update(1)
                        continue

                    msg_dir = os.path.join(conv_dir, message_id)
                    _ensure_dir(msg_dir)

                    ok = _export_message_by_id(message_id, msg_dir)
                    if not ok:
                        print(
                            colored(
                                f"Failed to export message {message_id} in folder {folder_name}",
                                "red",
                            )
                        )
                        return -1
                    pbar.update(1)

    print(colored("Download complete.", "green"))
    return 0
