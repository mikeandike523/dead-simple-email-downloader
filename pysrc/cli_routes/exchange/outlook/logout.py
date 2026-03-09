import json
import os

import requests
from termcolor import colored

from pysrc.utils.summarize_response import summarize_response

PROVIDER = "exchange"
BASE_URL = "http://localhost:3000"


def _load_jwt():
    new_path = os.path.join(".dsed", "auth", f"{PROVIDER}.json")
    legacy_path = ".dsed/jwt.json"
    for path in (new_path, legacy_path):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("jwt"), path
            except Exception:
                pass
    return None, None


def _delete_local_jwt(jwt_path: str):
    if not os.path.exists(jwt_path):
        return False
    try:
        os.remove(jwt_path)
        return True
    except Exception:
        return False


def impl_exchange_outlook_logout():
    jwt, jwt_path = _load_jwt()
    if jwt:
        url = f"{BASE_URL}/api/auth/exchange/logout"
        headers = {"Authorization": f"Bearer {jwt}"}
        resp = summarize_response(
            requests.post(url, headers=headers, json={"provider": PROVIDER}, timeout=30)
        )
        if resp.ok:
            print(colored("Server session cleared.", "green"))
        elif resp.status == 401:
            print(colored("JWT expired or invalid; clearing local state only.", "yellow"))
        else:
            print(colored("Logout request failed:", "red"))
            print(str(resp))
            return -1
    else:
        print(colored("No local JWT found; nothing to revoke.", "yellow"))

    if jwt_path:
        deleted = _delete_local_jwt(jwt_path)
        if deleted:
            print(colored(f"Local JWT removed ({jwt_path}).", "green"))
        elif jwt is not None:
            print(colored("Failed to remove local JWT.", "red"))
            return -1

    return 0
