from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import json
import requests


@dataclass
class ResponseSummary:
    ok: bool
    status: int
    has_response_body: bool
    text: str
    data: Optional[Any] = None  # Present only if content type is JSON AND body parses
    
    def __str__(self) -> str:
        """
        Return a concise string representation of the response.
        Shows data if available (JSON), otherwise shows text.
        """
        status_indicator = "✓" if self.ok else "✗"
        parts = [f"{status_indicator} {self.status}"]
        
        if not self.has_response_body:
            parts.append("(no body)")
        elif self.data is not None:
            # JSON data is available, show it instead of raw text
            data_str = json.dumps(self.data, separators=(',', ':'))
            # Truncate if too long
            if len(data_str) > 200:
                data_str = data_str[:197] + "..."
            parts.append(f"JSON: {data_str}")
        elif self.text:
            # No JSON data, show text content
            text_preview = self.text.strip()
            if len(text_preview) > 200:
                text_preview = text_preview[:197] + "..."
            parts.append(f"Text: {text_preview}")
        
        return " | ".join(parts)

def _is_json_content_type(content_type: str) -> bool:
    """
    Return True if the content type indicates JSON.
    Handles values like:
      - "application/json"
      - "application/ld+json"
      - "application/json; charset=utf-8"
    """
    if not content_type:
        return False
    # Take the media type portion before any parameters.
    media_type = content_type.split(";", 1)[0].strip().lower()
    # Match application/json or any */*+json (e.g., application/ld+json).
    if media_type == "application/json":
        return True
    # Split type/subtype and check +json suffix on subtype.
    if "/" in media_type:
        _type, subtype = media_type.split("/", 1)
        if subtype.endswith("+json"):
            return True
    return False


def summarize_response(resp: requests.Response) -> ResponseSummary:
    """
    Summarize a requests.Response according to the rules:
      - ok: resp.ok
      - status: resp.status_code
      - has_response_body: True if any bytes present
      - text: always set (empty string if no body)
      - data: only set when Content-Type is JSON AND body is valid JSON; else None
    """
    # Detect body presence using raw bytes to avoid decoding issues.
    body_bytes = resp.content or b""
    has_body = len(body_bytes) > 0

    # Always provide text; requests will decode using apparent/declared encoding.
    # If there's no body, make it an empty string.
    text = resp.text if has_body else ""

    # Only attempt JSON parse when Content-Type explicitly indicates JSON.
    content_type = resp.headers.get("Content-Type", "")
    data: Optional[Any] = None
    if has_body and _is_json_content_type(content_type):
        try:
            # Parse from text so we honor requests' decoding (charset, etc.)
            data = json.loads(text)
        except (ValueError, TypeError):
            # If header says JSON but it isn't parseable, leave data=None and keep text.
            data = None

    return ResponseSummary(
        ok=resp.ok,
        status=resp.status_code,
        has_response_body=has_body,
        text=text,
        data=data,
    )