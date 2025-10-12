import os
import json

from termcolor import colored

from pysrc.call_route import call_route

INDEX_SANITY_CHECK_MAX_DISCREPANCY = 100

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

def index_folder_get_top_level_metadata(folder_name,node):
    if not os.path.isfile(f".dsed/index/top-level-message-metadata/{node['id']}.json"):
        if not os.path.isfile(f".dsed/index/top-level-messages/{node['id']}.json"):
            print(colored(f"""\
Top level message ID list missing for folder "{folder_name}", a previous step may have failed. Try resetting the index and running indexing again.
                          ""","red"))
            return False
        with open(f".dsed/index/top-level-messages/{node['id']}.json", "r", encoding="utf-8") as f:
            message_ids = json.load(f)

        
    return True
