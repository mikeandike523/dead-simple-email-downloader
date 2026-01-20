from termcolor import colored

from pysrc.call_route import call_route


def _flatten_folders(folder_forest):
    folders = []

    def recursion(node, prior):
        path = " -> ".join(prior + (node["name"],))
        folders.append((path, node))
        for child in node.get("children", []):
            recursion(child, prior + (node["name"],))

    for folder in folder_forest:
        recursion(folder, tuple())

    return folders


def _count_color(count):
    if count is None:
        return "red"
    if count == 0:
        return "yellow"
    if count < 50:
        return "green"
    if count < 1000:
        return "cyan"
    return "magenta"


def impl_outlook_total_emails():
    resp = call_route(
        "/outlook/indexing/get-folders",
        "Fetching folder info...",
        save_debug_to=".dsed/debug/folders.json",
    )
    if resp is None:
        return -1

    folder_forest = resp.data or []
    folders = _flatten_folders(folder_forest)

    if not folders:
        print(colored("No folders found.", "red"))
        return -1

    rows = []
    total = 0
    for i, (folder_path, node) in enumerate(folders):
        folder_id = node.get("id")
        if not folder_id:
            print(colored(f"Missing folder id for {folder_path}", "red"))
            return -1

        resp_meta = call_route(
            "/outlook/indexing/get-folder-metadata",
            f"Fetching counts {i+1}/{len(folders)}: {folder_path}",
            json_body={"folderId": folder_id},
        )
        if resp_meta is None:
            return -1

        counts = resp_meta.data.get("counts") if resp_meta.data else {}
        count = counts.get("totalItemCount")
        if isinstance(count, int):
            total += count
        rows.append((folder_path, count))

    width = max(len("Folder"), max(len(path) for path, _ in rows))
    header = f"{'Folder':<{width}}  {'Count':>10}"
    print("\n" + colored(header, "green"))
    print(colored("-" * (width + 12), "green"))

    for folder_path, count in rows:
        count_display = "?" if count is None else f"{count}"
        print(
            colored(folder_path, "blue")
            + " " * (width - len(folder_path) + 2)
            + colored(f"{count_display:>10}", _count_color(count))
        )

    print(colored("-" * (width + 12), "green"))
    print(colored(f"{'TOTAL':<{width}}  {total:>10}", "green"))
    return 0
