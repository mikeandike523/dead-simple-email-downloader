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

from pysrc.cli_routes.outlook.login import impl_outlook_login

INDEX_SANITY_CHECK_MAX_DISCREPANCY = 100


@click.group()
def cli():
    pass


@cli.group("outlook")
def outlook():
    pass


@outlook.command("login")
def outlook_login():
    impl_outlook_login()


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
    resp = call_route(
        "/outlook/indexing/get-folders",
        "Fetching folder info...",
        save_debug_to=".dsed/debug/folders.json",
    )
    if resp is None:
        return -1


def index_folder_get_top_level_ids(node):
    if not os.path.isfile(f".dsed/index/top-level-messages/{node['id']}.json"):
        resp = call_route(
            "/outlook/indexing/get-id-list",
            "Fetching folder info...",
            method="POST",
            json_body={
                "folderId": node["id"],
            },
        )
        if resp is None:
            return False
        if not isinstance(resp.data, dict):
            print(
                colored(
                    "Got successful HTTP status but invalid response data.",
                    "red",
                )
            )
            return False
        message_ids = resp.data["messageIds"]
        print(f"Discovered {len(message_ids)} so far...")
        next_link = resp.data.get("nextLink", None)
        while next_link:
            resp = call_route(
                "/outlook/indexing/get-id-list",
                "Fetching more message IDs...",
                method="POST",
                json_body={
                    "folderId": node["id"],
                    "nextLink": next_link,
                },
            )
            if resp is None:
                return False
            if not isinstance(resp.data, dict):
                print(
                    colored(
                        "Got successful HTTP status but invalid response data.",
                        "red",
                    )
                )
                return False
            message_ids.extend(resp.data["messageIds"])
            print(f"Discovered {len(message_ids)} so far...")
            next_link = resp.data.get("nextLink", None)
        with open(
            f".dsed/index/top-level-messages/{node['id']}.json", "w", encoding="utf-8"
        ) as f:
            f.write(json.dumps(message_ids))
            print(
                colored(
                    f"Indexed messages in folder {node['name']} ({node['id']}).",
                    "green",
                )
            )
        with open(
            f".dsed/index/top-level-messages/{node['id']}.json", "r", encoding="utf-8"
        ) as f:
            message_ids = json.load(f)

    return True


def index_folder_sanity_check(node):

    top_level_messages_path = f".dsed/index/top-level-messages/{node['id']}.json"
    if not os.path.isfile(top_level_messages_path):
        print(
            colored(
                f"No top-level messages found in folder {node['name']} ({node['id']}). Fatal error.",
                "red",
            )
        )
        print(colored("Check that previous steps ran correctly.", "red"))
        return False
    folder_metadata = call_route(
        "/outlook/indexing/get-folder-metadata",
        "Fetching folder metadata...",
        method="POST",
        json_body={"folderId": node["id"]},
    )
    if folder_metadata is None:
        return False
    if (
        not isinstance(folder_metadata.data, dict)
        or not isinstance(folder_metadata.data["counts"], dict)
        or not isinstance(folder_metadata.data["counts"]["totalItemCount"], int)
    ):
        print(
            colored(
                "Got successful HTTP status but invalid response data.",
                "red",
            )
        )
    totalItemCount = folder_metadata.data["counts"]["totalItemCount"]
    with open(top_level_messages_path, "r", encoding="utf-8") as f:
        message_ids = json.load(f)
    indexedItemCount = len(message_ids)
    print(f"Indexed: {indexedItemCount}\tTotal: {totalItemCount}")
    if indexedItemCount < totalItemCount:
        print(
            f"{totalItemCount - indexedItemCount} messages may have arrived or been moved in since indexing started."
        )
    if indexedItemCount > totalItemCount:
        print(
            f"{indexedItemCount - totalItemCount} messages may have been deleted or moved since indexing started."
        )
    if abs(indexedItemCount - totalItemCount) > INDEX_SANITY_CHECK_MAX_DISCREPANCY:
        print(
            colored(
                f"Error: Index discrepancy of at least {INDEX_SANITY_CHECK_MAX_DISCREPANCY} detected! This could indicate that emails have arrived or been moved in since indexing started.",
                "red",
            )
        )
        return False
    print("Checking id uniqueness...")
    message_ids_set = set(message_ids)
    if len(message_ids) != len(message_ids_set):
        print(
            colored(
                f"Error: Duplicated message IDs detected! This could indicate that emails have arrived or been moved in since indexing started.",
                "red",
            )
        )
        return False
    print("No duplicate message ids.")
    return True


@outlook.command("index")
@click.option("--reset", is_flag=True, default=False, help="Reset the index.")
def outlook_index(reset=False):
    if reset:
        if os.path.isdir(".dsed/index"):
            shutil.rmtree(".dsed/index")
        os.makedirs(".dsed/index", exist_ok=True)
        print(colored("Index reset. Deleted all index files.", "green"))
        return 0
    try:

        if not os.path.isfile(".dsed/index/folders.json"):
            resp_folders = call_route(
                "/outlook/indexing/get-folders", "Fetching folder info..."
            )
            if resp_folders is None:
                return -1
            folder_data = resp_folders.data

            with open(".dsed/index/folders.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(resp_folders.data, indent=2))
                print(
                    colored(
                        "Folder information saved to.dsed/index/folders.json", "green"
                    )
                )

        with open(".dsed/index/folders.json", "r", encoding="utf-8") as f:
            folder_data = json.load(f)

        os.makedirs(".dsed/index/top-level-messages", exist_ok=True)

        folders = []

        def recursion(node, prior):
            folders.append(("\u2192".join(prior + (node["name"],)), node))
            for child in node["children"]:
                recursion(child, prior + (node["name"],))

        for folder in folder_data:
            recursion(folder, tuple())

        print(f"Found {len(folders)} folders:")
        for folder_name, _ in folders:
            print("\t" + folder_name)

        for i, (folder_name, node) in enumerate(folders):
            print(
                f"Getting Top Level IDs for Folder {i+1}/{len(folders)}: {folder_name}"
            )

            if not index_folder_get_top_level_ids(node):
                print(colored(f"Failed to get top level IDs for {folder_name}", "red"))
                return -1

        print(colored("All folders top-level-indexed successfully.", "green"))

        print("Performing sanity checks...")

        for i, (folder_name, node) in enumerate(folders):
            print(f"Sanity Check for Folder {i+1}/{len(folders)}: {folder_name}")

            if not index_folder_sanity_check(node):
                print(colored(f"Sanity check failed for {folder_name}", "red"))
                return -1

        return 0

    except KeyboardInterrupt:
        print("Process aborted by user.")
        return -1


if __name__ == "__main__":
    cli()
