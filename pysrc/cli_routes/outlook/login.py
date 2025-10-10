import json
from time import sleep
import webbrowser

import requests
from termcolor import colored


from pysrc.utils.summarize_response import summarize_response
from pysrc.call_route import call_route


def impl_outlook_login():
    resp = summarize_response(
        requests.get("http://localhost:3000/api/auth/outlook/get-url")
    )

    if not resp.ok:
        print(colored("Failed to get authorization URL:", "red"))
        print(str(resp))
        return -1

    if not isinstance(resp.data, dict):
        print(colored("Invalid response from server:", "red"))
        print(str(resp))
        return -1

    authorize_url = resp.data.get("url")
    poll_token = resp.data.get("pollToken")

    if not isinstance(authorize_url, str) or not authorize_url:
        print(colored("Invalid authorization URL:", "red"))
        print(authorize_url)
        return -1

    webbrowser.open_new_tab(authorize_url)

    print("If the url did not automatically open, enter the following link manually:")

    print("")

    # print blue and underlined
    print(colored(authorize_url, "blue", attrs=["underline"]))

    print("")

    login_complete = False

    anim_index = 0

    anims = ["/", "-", "\\", "|"]

    try:
        while not login_complete:
            print("\r", end="")
            print(anims[anim_index], end="")
            anim_index = (anim_index + 1) % len(anims)
            sleep(0.2)
            resp = summarize_response(
                requests.post(
                    "http://localhost:3000/api/auth/outlook/check-pending-login",
                    json=poll_token,
                )
            )
            if resp.ok:
                login_complete = True
                if not resp.data:
                    print(
                        colored(
                            "Got successful HTTP status but invalid response body.",
                            "red",
                        )
                    )
                    return -1
                if not isinstance(resp.data, dict):
                    print(
                        colored(
                            "Got successful HTTP status but invalid response data.",
                            "red",
                        )
                    )
                    return -1

                print(colored("\nLogin successful!", "green"))

                with open(".dsed/jwt.json", "w", encoding="utf-8") as f:
                    f.write(json.dumps(resp.data))
                    print(colored("JWT saved to .dsed/jwt.json", "green"))
            else:
                if resp.status != 403:  # 403 is known error case -> not logged in yet
                    print(
                        colored(
                            f"Unexpected error response (status={resp.status}):", "red"
                        )
                    )
                    return -1
    except KeyboardInterrupt:
        print("")
        print("Login cancelled by user.")
        return -1