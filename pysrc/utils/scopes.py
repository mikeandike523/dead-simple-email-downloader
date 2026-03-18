"""
Python-side scope registry — source of truth for OAuth scopes.

Next.js get-url endpoints accept a `scopes` query param (space-separated)
built here, so scope changes never require a backend rebuild.
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, dict[str, dict]] = {
    "exchange": {
        "outlook": {
            "base": [
                "openid",
                "offline_access",
                "User.Read",
                "Mail.Read",
            ],
            "commands": {
                "me":              [],
                "folders":         [],
                "index":           [],
                "total-emails":    [],
                "output":          [],
                "debug-download":  [],
                "download":        ["Mail.Read.Shared"],
                "safe-delete":     ["Mail.ReadWrite", "Mail.ReadWrite.Shared"],
            },
        },
    },
    "google": {
        "gmail": {
            "base": [
                "openid",
                "email",
                "profile",
                "https://www.googleapis.com/auth/gmail.readonly",
            ],
            "commands": {
                "me":       [],
                "folders":  [],
                "list":     [],
                "download": [],
                # Categorising / moving / deleting — needs modify + full access for hard-delete
                "manage":   [
                    "https://www.googleapis.com/auth/gmail.modify",
                    "https://mail.google.com/",
                ],
            },
        },
        "drive": {
            "base": [
                "openid",
                "email",
                "profile",
                "https://www.googleapis.com/auth/drive.readonly",
            ],
            "commands": {},
        },
    },
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def resolve_scopes(
    provider: str,
    product: str,
    commands: Optional[list[str]] = None,
) -> list[str]:
    """Return deduplicated union of base scopes + any extra scopes for the given commands."""
    entry = _REGISTRY.get(provider, {}).get(product)
    if not entry:
        return []
    extra = [s for cmd in (commands or []) for s in entry["commands"].get(cmd, [])]
    seen: set[str] = set()
    result: list[str] = []
    for s in entry["base"] + extra:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def describe_scope_request(
    provider: str,
    product: str,
    commands: Optional[list[str]] = None,
) -> dict:
    """Return a breakdown dict suitable for --summarize-scopes output."""
    entry = _REGISTRY.get(provider, {}).get(product)
    if not entry:
        return {
            "base": [],
            "allCommandScopes": {},
            "selectedCommandScopes": {},
            "resolved": [],
            "unknownCommands": list(commands or []),
        }

    all_command_scopes: dict[str, list[str]] = dict(entry["commands"])
    selected_command_scopes: dict[str, list[str]] = {}
    unknown_commands: list[str] = []

    for cmd in (commands or []):
        if cmd in entry["commands"]:
            selected_command_scopes[cmd] = entry["commands"][cmd]
        else:
            unknown_commands.append(cmd)

    return {
        "base": list(entry["base"]),
        "allCommandScopes": all_command_scopes,
        "selectedCommandScopes": selected_command_scopes,
        "resolved": resolve_scopes(provider, product, commands),
        "unknownCommands": unknown_commands,
    }


def list_providers() -> list[str]:
    return list(_REGISTRY.keys())


def list_products(provider: str) -> list[str]:
    return list(_REGISTRY.get(provider, {}).keys())
