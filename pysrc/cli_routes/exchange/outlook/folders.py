from pysrc.call_route import call_route


def impl_exchange_outlook_folders():
    resp = call_route(
        "/exchange/outlook/indexing/get-folders",
        "Fetching folder info...",
        save_debug_to=".dsed/debug/folders.json",
        provider="exchange",
    )
    if resp is None:
        return -1
    return 0
