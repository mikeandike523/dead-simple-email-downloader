import os
import json
import base64
import binascii

from termcolor import colored

from pysrc.call_route import call_route
from pysrc.helpers.shortcodes import build_shortcode_map

INDEX_SANITY_CHECK_MAX_DISCREPANCY = 100
INDEX_GET_METADATA_CHUNK_SIZE = 20
def _resolve_index_file(base_dir: str, folder_id: str, folder_shortcode: str) -> str:
    os.makedirs(base_dir, exist_ok=True)
    new_path = os.path.join(base_dir, f"{folder_shortcode}.json")
    old_path = os.path.join(base_dir, f"{folder_id}.json")
    if not os.path.isfile(new_path) and os.path.isfile(old_path):
        with open(old_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(new_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return new_path

def _decode_conversation_index(b64: str) -> bytes:
    """Decode Graph's Base64 conversationIndex to raw bytes; robust to missing padding."""
    if not b64:
        return b""
    s = b64.strip()
    s += "=" * ((4 - (len(s) % 4)) % 4)
    try:
        return base64.b64decode(s)
    except binascii.Error:
        # Some payloads might be URL-safe base64
        return base64.urlsafe_b64decode(s)


def index_folder_get_top_level_ids(node):
    folder_id = node.get("id")
    folder_shortcode = node.get("shortcode")
    if not folder_id or not folder_shortcode:
        print(colored("Missing folder id or shortcode during indexing.", "red"))
        return False
    target_path = _resolve_index_file(
        ".dsed/index/top-level-messages", folder_id, folder_shortcode
    )
    if not os.path.isfile(target_path):
        resp = call_route(
            "/outlook/indexing/get-id-list",
            "Fetching folder info...",
            method="POST",
            json_body={
                "folderId": folder_id,
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
            target_path, "w", encoding="utf-8"
        ) as f:
            f.write(json.dumps(message_ids))
            print(
                colored(
                    f"Indexed messages in folder {node['name']} ({folder_id}).",
                    "green",
                )
            )
    return True


def index_folder_sanity_check(node):
    folder_id = node.get("id")
    folder_shortcode = node.get("shortcode")
    if not folder_id or not folder_shortcode:
        print(colored("Missing folder id or shortcode during sanity check.", "red"))
        return False
    top_level_messages_path = _resolve_index_file(
        ".dsed/index/top-level-messages", folder_id, folder_shortcode
    )
    if not os.path.isfile(top_level_messages_path):
        print(
            colored(
                f"No top-level messages found in folder {node['name']} ({folder_id}). Fatal error.",
                "red",
            )
        )
        print(colored("Check that previous steps ran correctly.", "red"))
        return False
    folder_metadata = call_route(
        "/outlook/indexing/get-folder-metadata",
        "Fetching folder metadata...",
        method="POST",
        json_body={"folderId": folder_id},
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

def index_folder_get_top_level_metadata(folder_name, node):
    folder_id = node.get("id")
    folder_shortcode = node.get("shortcode")
    if not folder_id or not folder_shortcode:
        print(colored("Missing folder id or shortcode for metadata.", "red"))
        return False
    metadata_path = _resolve_index_file(
        ".dsed/index/top-level-message-metadata", folder_id, folder_shortcode
    )
    if not os.path.isfile(metadata_path):
        messages_path = _resolve_index_file(
            ".dsed/index/top-level-messages", folder_id, folder_shortcode
        )
        if not os.path.isfile(messages_path):
            print(colored(f"""\
Top level message ID list missing for folder "{folder_name}", a previous step may have failed.
Try resetting the index and running indexing again.
                          ""","red"))
            return False
        with open(messages_path, "r", encoding="utf-8") as f:
            message_ids = json.load(f)
        message_ids_chunked = []

        for i in range(0, len(message_ids), INDEX_GET_METADATA_CHUNK_SIZE):
            message_ids_chunked.append(message_ids[i:i + INDEX_GET_METADATA_CHUNK_SIZE])

        all_message_metadata = {}

        for chunk_index, chunk_ids in enumerate(message_ids_chunked):
            print(f"Fetching metadata for chunk {chunk_index+1}/{len(message_ids_chunked)}...")

            metadata_response = call_route("/outlook/indexing/hydrate-message-metadata", "Fetching metadata for messages...", method="POST", json_body={
                "ids": chunk_ids,
                "includeHeaders": False,
                "includeEpoch": True,
            })

            if metadata_response is None:
                return False
            
            if not isinstance(metadata_response.data, dict) or not isinstance(metadata_response.data["messages"], list):
                print(colored("Got successful HTTP status but invalid response data.", "red"))
                return False
            
            for message_id, message_metadata in zip(chunk_ids, metadata_response.data["messages"]):
                all_message_metadata[message_id] = message_metadata
            
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(all_message_metadata))

        
    return True


def index_folder_organize_into_conversations(folder_name, node):
    # 1) Load top-level metadata produced by an earlier step
    folder_id = node.get("id")
    folder_shortcode = node.get("shortcode")
    if not folder_id or not folder_shortcode:
        print(colored("Missing folder id or shortcode for conversations.", "red"))
        return False
    input_path = _resolve_index_file(
        ".dsed/index/top-level-message-metadata", folder_id, folder_shortcode
    )
    if not os.path.isfile(input_path):
        print(colored(f"""\
Top level message metadata list missing for folder "{folder_name}", a previous step may have failed.
Try resetting the index and running indexing again.
""", "red"))
        return False

    with open(input_path, "r", encoding="utf-8") as f:
        message_metadata = json.load(f)

    # 5) Write out an organized artifact (non-destructive, separate from input)
    out_dir = ".dsed/index/conversations-organized"
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, f"{folder_shortcode}.json")

    if os.path.isfile(output_path):
        return True

    # 2) Group by conversationId
    conversation_groups = {}
    for meta in message_metadata.values():
        cid = meta.get("conversationId")
        if not cid:
            # Skip items with no conversationId (rare, but defensively handle)
            # Could also bucket them under a sentinel key if desired.
            continue
        conversation_groups.setdefault(cid, []).append(meta)

    # 3) Sort each group internally by conversationIndex latest -> oldest
    #    Outlook/Exchange ordering is achieved by bytewise comparison of conversationIndex.
    #    Ascending bytes = oldest->newest, so we sort ascending then reverse (or sort descending).
    for cid, metas in conversation_groups.items():
        def inner_key(m):
            idx_bytes = _decode_conversation_index(m.get("conversationIndex", ""))
            # As a stable tie-breaker, use receivedEpoch (ascending = older first),
            # then id to ensure deterministic ordering.
            # We'll reverse the whole group later to get latest->oldest.
            return (idx_bytes, m.get("receivedEpoch", 0), m.get("id", ""))

        metas.sort(key=inner_key)
        metas.reverse()  # latest -> oldest

    # 4) Sort groups by the receivedEpoch of the first message (already latest in that group)
    #    If missing, treat as 0 so those groups fall to the end.
    def group_sort_key(item):
        cid, metas = item
        first = metas[0] if metas else {}
        return first.get("receivedEpoch", 0)

    # Create a list of (conversationId, [messages...]) sorted latest->oldest by group
    sorted_conversations = sorted(conversation_groups.items(), key=group_sort_key, reverse=True)

    conversation_ids = [cid for cid, _ in sorted_conversations if cid]
    conv_id_to_shortcode, conv_shortcode_to_id, conv_length = build_shortcode_map(
        conversation_ids
    )

    result = []
    for cid, metas in sorted_conversations:
        message_ids = [m.get("id") for m in metas if m.get("id")]
        msg_id_to_shortcode, msg_shortcode_to_id, msg_length = build_shortcode_map(
            message_ids
        )
        for meta in metas:
            message_id = meta.get("id")
            if message_id:
                meta["shortcode"] = msg_id_to_shortcode.get(message_id)
        result.append(
            {
                "conversationId": cid,
                "conversationShortcode": conv_id_to_shortcode.get(cid),
                "messageShortcodes": msg_shortcode_to_id,
                "messageShortcodeLength": msg_length,
                "messages": metas,
            }
        )

    output_payload = {
        "folderId": folder_id,
        "folderShortcode": folder_shortcode,
        "conversationShortcodes": conv_shortcode_to_id,
        "conversationShortcodeLength": conv_length,
        "conversations": result,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    print(colored(f'Organized {len(result)} conversation group(s) for folder "{folder_name}" -> {output_path}', "green"))
    return True
