from termcolor import colored

from pysrc.call_route import call_route

def impl_outlook_me():
    resp = call_route("/outlook/me", "Fetching user info...")
    if resp is None:
        return -1
    print(colored("\nUser information:", "green"))
    user_data = resp.data
    for key, value in user_data.items():
        print(f"{key}: {value}")
    return 0
