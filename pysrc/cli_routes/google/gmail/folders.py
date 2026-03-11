from termcolor import colored

from pysrc.call_route import call_route


def impl_google_gmail_folders():
    resp = call_route("/google/gmail/folders", "Fetching labels...", provider="google")
    if resp is None:
        return -1

    folders = (resp.data or {}).get("folders", [])
    if not folders:
        print(colored("No labels found.", "yellow"))
        return 0

    # Split into system labels and user labels for cleaner display
    system = [f for f in folders if f.get("type") == "system"]
    user   = [f for f in folders if f.get("type") != "system"]

    # Sort each group by name
    system.sort(key=lambda f: f["name"].lower())
    user.sort(key=lambda f: f["name"].lower())

    def _print_group(group: list, title: str):
        if not group:
            return
        col_name  = max(len(f["name"]) for f in group)
        col_name  = max(col_name, len("Label"))

        header = (
            f"  {'Label':<{col_name}}  {'Total':>8}  {'Unread':>8}  {'Read':>8}"
        )
        print(colored(f"\n{title}", "cyan"))
        print(colored(header, "dark_grey"))
        print(colored("  " + "-" * (col_name + 30), "dark_grey"))

        for f in group:
            name   = f["name"]
            total  = f["total"]
            unread = f["unread"]
            read   = f["read"]

            unread_str = colored(f"{unread:>8}", "yellow") if unread > 0 else f"{unread:>8}"
            print(f"  {name:<{col_name}}  {total:>8}  {unread_str}  {read:>8}")

    _print_group(system, "System labels")
    _print_group(user,   "User labels")
    print()

    return 0
