"""
Synchronous HTTP helpers for the Gmail Manage TUI.

These functions are intentionally print-free so they can be called from
Textual worker threads without polluting the TUI's alternate screen.
"""
from __future__ import annotations

import json
import os
from typing import Optional
from urllib.parse import urlencode

import requests

from pysrc.utils.backend_port import get_backend_port

_BASE_URL: str | None = None

TRASH_LABEL_ID = "TRASH"


def _base_url() -> str:
    global _BASE_URL
    if _BASE_URL is None:
        _BASE_URL = f"http://localhost:{get_backend_port()}"
    return _BASE_URL


def _get_jwt(provider: str = "google") -> str:
    new_path = os.path.join(".dsed", "auth", f"{provider}.json")
    legacy_path = os.path.join(".dsed", "jwt.json")

    if os.path.exists(new_path):
        path = new_path
    elif os.path.exists(legacy_path):
        path = legacy_path
    else:
        raise RuntimeError(
            f"Not logged in for provider '{provider}'. "
            f"Run 'dsed google gmail login -c manage' first."
        )

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    jwt = data.get("jwt")
    if not jwt:
        raise RuntimeError("JWT file is malformed.")
    return jwt


def _api(method: str, route: str, provider: str = "google", **kwargs) -> dict:
    jwt = _get_jwt(provider)
    url = f"{_base_url()}/api/{route.lstrip('/')}"
    headers = {"Authorization": f"Bearer {jwt}"}
    resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    if resp.status_code == 401:
        raise RuntimeError(
            "JWT expired or invalid. Run 'dsed google gmail login -c manage' again."
        )
    if not resp.ok:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_labels() -> list[dict]:
    """Fetch all Gmail labels, excluding the Trash label."""
    data = _api("GET", "/google/gmail/folders")
    folders = data.get("folders", [])
    return [f for f in folders if f.get("id") != TRASH_LABEL_ID]


def fetch_inbox(page_token: Optional[str] = None) -> dict:
    """Fetch a page of inbox emails. Returns {emails, nextPageToken, total}."""
    params = {}
    if page_token:
        params["pageToken"] = page_token
    return _api("GET", "/google/gmail/manage/inbox", params=params)


def fetch_categories() -> list[dict]:
    """Fetch all categories from DB. Returns [{id, name}, ...]."""
    data = _api("GET", "/google/gmail/manage/categories")
    return data.get("categories", [])


def create_category(name: str) -> dict:
    """Create or retrieve a category (normalized to lowercase). Returns {id, name}."""
    data = _api("POST", "/google/gmail/manage/categories", json={"name": name})
    return data["category"]


_SUBJECT_MAX    = 256
_PREVIEW_MAX    = 512
_FROM_MAX       = 512
_LABEL_NAME_MAX = 255


def _trunc(value: str | None, max_chars: int) -> str | None:
    """Truncate by Unicode code point (not byte) to match the backend's approach."""
    if value is None:
        return None
    chars = list(value)  # list() iterates code points in Python
    return "".join(chars[:max_chars])


def assign_category(
    message_id: str,
    category_id: int,
    subject: str | None = None,
    body_preview: str | None = None,
    from_address: str | None = None,
) -> None:
    """Assign a category to a message, upserting email_content and recording the assignment."""
    _api(
        "POST",
        "/google/gmail/manage/assign",
        json={
            "messageId":   message_id,
            "categoryId":  category_id,
            "subject":     _trunc(subject,      _SUBJECT_MAX),
            "bodyPreview": _trunc(body_preview, _PREVIEW_MAX),
            "fromAddress": _trunc(from_address, _FROM_MAX),
        },
    )


def record_action(
    message_id: str,
    action: str,
    label_id: str | None = None,
    label_name: str | None = None,
    subject: str | None = None,
    body_preview: str | None = None,
    from_address: str | None = None,
) -> None:
    """Record the disposition taken on a message for ML training signal."""
    _api(
        "POST",
        "/google/gmail/manage/action",
        json={
            "messageId":   message_id,
            "action":      action,
            "labelId":     label_id,
            "labelName":   _trunc(label_name,   _LABEL_NAME_MAX),
            "subject":     _trunc(subject,      _SUBJECT_MAX),
            "bodyPreview": _trunc(body_preview, _PREVIEW_MAX),
            "fromAddress": _trunc(from_address, _FROM_MAX),
        },
    )


def soft_delete(message_id: str) -> None:
    """Move a message to Gmail Trash."""
    _api("POST", "/google/gmail/manage/trash", json={"messageId": message_id})


def hard_delete(message_id: str) -> None:
    """Permanently delete a message."""
    route = f"/google/gmail/manage/delete?{urlencode({'messageId': message_id})}"
    _api("DELETE", route)


def move_to_label(message_id: str, label_id: str) -> None:
    """Move a message to a Gmail label (and remove from INBOX)."""
    _api("POST", "/google/gmail/manage/move", json={"messageId": message_id, "labelId": label_id})


def fetch_email_body(message_id: str) -> dict:
    """Fetch the full HTML/text body of a message. Returns {html: ...} or {text: ...}."""
    route = f"/google/gmail/manage/body?{urlencode({'messageId': message_id})}"
    return _api("GET", route)
