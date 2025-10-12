import os
import shutil
import json

from termcolor import colored

from pysrc.call_route import call_route
from pysrc.helpers.outlook.indexing import index_folder_get_top_level_ids, index_folder_sanity_check

def impl_outlook_index(reset=False):
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

