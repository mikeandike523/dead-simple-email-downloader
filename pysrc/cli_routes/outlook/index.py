import os
import shutil
import json

from termcolor import colored

from pysrc.call_route import call_route
from pysrc.helpers.outlook.indexing import (
    index_folder_get_top_level_ids,
    index_folder_sanity_check,
    index_folder_get_top_level_metadata,
    index_folder_organize_into_conversations,
)


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
            if folder_data is None:
                folder_data = []
        else:
            with open(".dsed/index/folders.json", "r", encoding="utf-8") as f:
                folder_data = json.load(f)

        from pysrc.helpers.shortcodes import (
            apply_folder_shortcodes,
            build_shortcode_map,
            collect_folder_nodes,
            write_shortcode_map,
        )

        nodes = collect_folder_nodes(folder_data)
        folder_ids = [node.get("id") for node in nodes if node.get("id")]
        id_to_shortcode, shortcode_to_id, length = build_shortcode_map(folder_ids)
        apply_folder_shortcodes(folder_data, id_to_shortcode)
        write_shortcode_map(
            ".dsed/index/shortcodes/folders.json",
            id_to_shortcode,
            shortcode_to_id,
            length,
        )

        with open(".dsed/index/folders.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(folder_data, indent=2))
            print(
                colored(
                    "Folder information saved to.dsed/index/folders.json", "green"
                )
            )

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

        print("Getting top level message IDs...")

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

        print("Fetching top-level message metadata...")

        os.makedirs(".dsed/index/top-level-message-metadata", exist_ok=True)

        for i, (folder_name, node) in enumerate(folders):
            print(
                f"Fetching Top Level Metadata for Folder {i+1}/{len(folders)}: {folder_name}"
            )

            if not index_folder_get_top_level_metadata(folder_name, node):
                print(
                    colored(
                        f"Failed to fetch top level metadata for {folder_name}", "red"
                    )
                )
                return -1

        print("Organizing into conversations...")

        for i, (folder_name, node) in enumerate(folders):
            print(
                f"Organizing into Conversations for Folder {i+1}/{len(folders)}: {folder_name}"
            )
            if not index_folder_organize_into_conversations(folder_name, node):
                print(
                    colored(
                        f"Failed to organize into conversations for {folder_name}",
                        "red",
                    )
                )
                return -1

        return 0

    except KeyboardInterrupt:
        print("Process aborted by user.")
        return -1
