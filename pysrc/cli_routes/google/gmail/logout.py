import requests
from termcolor import colored

from pysrc.utils.summarize_response import summarize_response
from pysrc.utils.backend_port import get_backend_port
from pysrc.call_route import _load_jwt, _delete_local_jwt

PROVIDER = "google"
BASE_URL = f"http://localhost:{get_backend_port()}"


def impl_google_gmail_logout():
    jwt, jwt_path = _load_jwt(PROVIDER)
    if jwt:
        url = f"{BASE_URL}/api/auth/google/logout"
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
