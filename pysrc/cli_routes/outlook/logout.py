import json
import os

import requests
from termcolor import colored

from pysrc.call_route import BASE_URL, JWT_PATH
from pysrc.utils.summarize_response import summarize_response


def _load_jwt(jwt_path: str):
    if not os.path.exists(jwt_path):
        return None
    try:
        with open(jwt_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("jwt")
    except Exception:
        return None


def _delete_local_jwt(jwt_path: str):
    if not os.path.exists(jwt_path):
        return False
    try:
        os.remove(jwt_path)
        return True
    except Exception:
        return False


def impl_outlook_logout():
    jwt = _load_jwt(JWT_PATH)
    if jwt:
        url = f"{BASE_URL.rstrip('/')}/api/auth/outlook/logout"
        headers = {"Authorization": f"Bearer {jwt}"}
        resp = summarize_response(
            requests.post(url, headers=headers, timeout=30)
        )
        if resp.ok:
            print(colored("Server session cleared.", "green"))
        elif resp.status == 401:
            print(
                colored(
                    "JWT expired or invalid; clearing local state only.",
                    "yellow",
                )
            )
        else:
            print(colored("Logout request failed:", "red"))
            print(str(resp))
            return -1
    else:
        print(colored("No local JWT found; nothing to revoke.", "yellow"))

    deleted = _delete_local_jwt(JWT_PATH)
    if deleted:
        print(colored("Local JWT removed.", "green"))
    else:
        if jwt is None:
            return 0
        print(colored("Failed to remove local JWT.", "red"))
        return -1

    return 0
