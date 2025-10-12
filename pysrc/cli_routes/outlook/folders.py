from pysrc.call_route import call_route

def impl_outlook_folders():
    resp = call_route(
        "/outlook/indexing/get-folders",
        "Fetching folder info...",
        save_debug_to=".dsed/debug/folders.json",
    )
    if resp is None:
        return -1
    return 0
