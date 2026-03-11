from termcolor import colored

from pysrc.call_route import call_route


def impl_google_gmail_me():
    resp = call_route("/google/gmail/me", "Fetching user info...", provider="google")
    if resp is None:
        return -1
    print(colored("\nUser information:", "green"))
    user_data = resp.data or {}
    for key, value in user_data.items():
        print(f"{key}: {value}")
    return 0
