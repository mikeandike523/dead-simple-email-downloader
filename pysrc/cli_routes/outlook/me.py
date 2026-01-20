from termcolor import colored

from pysrc.call_route import call_route

def impl_outlook_me():
    resp = call_route("/outlook/me", "Fetching user info...")
    if resp is None:
        return -1
    print(colored("\nUser information:", "green"))
    user_data = resp.data or {}
    graph_token = user_data.pop("graphAccessToken", None)
    for key, value in user_data.items():
        print(f"{key}: {value}")
    if isinstance(graph_token, dict):
        scopes = graph_token.get("scopes") or []
        roles = graph_token.get("roles") or []
        print(colored("\nGraph access token:", "cyan"))
        if scopes:
            print("scopes:")
            for item in scopes:
                print(f"  - {item}")
        else:
            print("scopes: (none)")
        if roles:
            print("roles:")
            for item in roles:
                print(f"  - {item}")
        else:
            print("roles: (none)")
        for key in ["aud", "appid", "tid", "oid", "iss", "version", "expiresAtUtc"]:
            if graph_token.get(key):
                print(f"{key}: {graph_token.get(key)}")
    return 0
