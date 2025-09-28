import json
import os
from time import sleep
import webbrowser
import shutil

import click
import requests
from termcolor import colored


from pysrc.utils.summarize_response import summarize_response
from pysrc.call_route import call_route


@click.group()
def cli():
    pass


@cli.group("outlook")
def outlook():
    pass


@outlook.command("login")
def outlook_login():
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


@outlook.command("me")
def outlook_me():
    resp = call_route("/outlook/me", "Fetching user info...")
    if resp is None:
        return -1
    print(colored("\nUser information:", "green"))
    user_data = resp.data
    for key, value in user_data.items():
        print(f"{key}: {value}")


@outlook.command("folders")
def outlook_folders():
    resp = call_route("/outlook/folders", "Fetching folder info...")
    if resp is None:
        return -1
    with open(".dsed/debug/folders.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(resp.data, indent=2))
        print(colored("Folder information saved to .dsed/debug/folders.json", "green"))

def index_folder(node):
    ...


@outlook.command("index")
def outlook_index():
    if os.path.isdir(".dsed/index"):
        shutil.rmtree(".dsed/index")
    os.makedirs(".dsed/index", exist_ok=True)
    resp_folders = call_route("/outlook/folders", "Fetching folder info...")
    with open(".dsed/index/folders.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(resp_folders.data, indent=2))
        print(colored("Folder information saved to.dsed/index/folders.json", "green"))
    folder_data = resp_folders.data
    folders = []

    def recursion(node, prior):
        folders.append(("\u2192".join(prior + (node["name"],)),node))
        for child in node["children"]:
            recursion(child, prior + (node["name"],))

    for folder in folder_data:
        recursion(folder, tuple())

    print(f"Found {len(folders)} folders:")
    for folder_name, _ in folders:
        print("\t"+folder_name)

    for i, (folder_name, node) in enumerate(folders):
        print(f"Indexing Folder {i+1}/{len(folders)}: {folder_name}")
        index_folder(node)


if __name__ == "__main__":
    cli()
