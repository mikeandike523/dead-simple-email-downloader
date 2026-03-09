import os
import json
import time
import threading
import requests
from termcolor import colored
from typing import Any, Dict, Iterable, List, Tuple, Optional, Union

from pysrc.utils.summarize_response import summarize_response

BASE_URL = "http://localhost:3000"  # change if needed
JWT_PATH = ".dsed/jwt.json"  # legacy path — kept for backward compat

# Assumes summarize_response(resp: requests.Response) -> object with .ok, .status, .text, .data
# You can keep your existing implementation.

def _flatten_params(params: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Flattens a dict of query params into a list of (key, value) tuples.
    - Lists/tuples become repeated keys: key=a&key=b
    - None values are skipped
    - Everything else is str()'d
    """
    if not params:
        return []
    out: List[Tuple[str, str]] = []
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            for item in v:
                if item is None:
                    continue
                out.append((k, str(item)))
        else:
            out.append((k, str(v)))
    return out

def _load_jwt(provider: str = "exchange") -> Optional[str]:
    """
    Load the CLI JWT for the given provider.
    Looks in .dsed/auth/<provider>.json first; falls back to legacy .dsed/jwt.json.
    """
    new_path = os.path.join(".dsed", "auth", f"{provider}.json")
    legacy_path = JWT_PATH

    # Prefer new namespaced path; fall back to legacy for existing users
    if os.path.exists(new_path):
        jwt_path = new_path
    elif os.path.exists(legacy_path):
        jwt_path = legacy_path
    else:
        print(colored(
            f"JWT not found for provider '{provider}'. "
            f"Run 'dsed {provider} outlook login' first.",
            "red",
        ))
        return None

    with open(jwt_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data.get("jwt")
        except Exception:
            print(colored("Failed to read JWT file.", "red"))
            return None

def _spinner_line(prompt: str):
    stop = threading.Event()
    def spinner():
        frames = "|/-\\"
        i = 0
        while not stop.is_set():
            print(f"\r{prompt} {frames[i % len(frames)]}", end="", flush=True)
            time.sleep(0.1)
            i += 1
    t = threading.Thread(target=spinner, daemon=True)
    return stop, t

def call_route(
    route: str,
    prompt: str = "working...",
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Union[Dict[str, Any], str, int, float, None]] = None,
    method: Optional[str] = None,
    save_debug_to: Optional[str] = None,  # e.g. ".dsed/debug/folders.json"
    provider: str = "exchange",
):
    """
    Generic caller for predictable backend routes.

    Args:
        route: e.g. "outlook/folders" (with or without leading/trailing slashes)
        prompt: text shown while spinning
        params: dict of query params (lists become repeated keys)
        json_body: dict sent as JSON (if provided and method not set, uses POST)
        method: force "GET"/"POST"/... If None, infer (POST if json_body else GET)
        save_debug_to: optional path to write resp.data prettified JSON on success
        provider: OAuth provider key used to load the correct JWT

    Returns:
        summarize_response(requests.Response)
    """
    jwt = _load_jwt(provider)
    if not jwt:
        return None

    url = f"{BASE_URL.rstrip('/')}/api/{route.lstrip('/')}"
    headers = {"Authorization": f"Bearer {jwt}"}

    # Determine HTTP method
    meth = method.upper() if method else ("POST" if json_body is not None else "GET")

    # Build query params with repeated keys for arrays
    query_tuples = _flatten_params(params or {})

    stop, t = _spinner_line(prompt)
    t.start()
    try:
        resp = requests.request(
            meth,
            url,
            headers=headers,
            params=query_tuples if query_tuples else None,
            json=json_body if json_body is not None else None,
            timeout=60,
        )
        summary = summarize_response(resp)
    finally:
        stop.set()
        t.join()

    if getattr(summary, "ok", False):
        print(f"\r{prompt} " + colored("success", "green"))
        if save_debug_to:
            os.makedirs(os.path.dirname(save_debug_to), exist_ok=True)
            with open(save_debug_to, "w", encoding="utf-8") as f:
                f.write(json.dumps(summary.data, indent=2))
            print(colored(f"Saved to {save_debug_to}", "green"))
    else:
        print(f"\r{prompt} " + colored("failed", "red"))
        # Persist server error body for debugging
        try:
            with open(".dsed/debug/error.txt", "w", encoding="utf-8") as f:
                f.write(summary.text)
        except Exception:
            pass

        if getattr(summary, "status", None) == 401:
            print(colored("JWT expired or invalid. Please login again.", "red"))
        else:
            print(colored("Request failed:", "red"))
            print(str(summary))

        return None

    return summary