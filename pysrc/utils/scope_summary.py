"""
CLI helper: fetch and pretty-print scope breakdown from the backend.
"""
import requests
from termcolor import colored

from pysrc.utils.summarize_response import summarize_response


def print_scope_summary(base_url: str, provider: str, product: str, commands: list[str]) -> int:
    """
    Calls /api/auth/{provider}/scopes and prints a human-readable breakdown.

    - No commands selected: shows base scopes + ALL known command scopes for reference.
    - Commands selected: shows base + selected command scopes + what each adds.

    Returns 0 on success, -1 on failure.
    """
    params: dict = {"product": product}
    if commands:
        params["commands"] = ",".join(commands)

    resp = summarize_response(
        requests.get(f"{base_url}/api/auth/{provider}/scopes", params=params)
    )
    if not resp.ok or not isinstance(resp.data, dict):
        print(colored("Failed to fetch scope information from server.", "red"))
        return -1

    d = resp.data
    base: list[str] = d.get("base", [])
    all_command_scopes: dict = d.get("allCommandScopes", {})
    selected_command_scopes: dict = d.get("selectedCommandScopes", {})
    resolved: list[str] = d.get("resolved", [])
    unknown: list[str] = d.get("unknownCommands", [])

    summarising_all = not commands

    header = f"\nScopes for {provider}/{product}"
    if summarising_all:
        header += " — all available command scopes (reference)"
    else:
        header += f" — selected commands: {', '.join(commands)}"
    print(colored(header, "cyan"))
    print()

    print(colored("  [base]", "yellow"))
    for s in base:
        print(f"    {s}")

    if summarising_all:
        # Show every known command as a reference
        for cmd, scopes in all_command_scopes.items():
            if scopes:
                print(colored(f"  [{cmd}]", "yellow") + colored("  +extra", "dark_grey"))
                for s in scopes:
                    print(f"    {s}")
            else:
                print(colored(f"  [{cmd}]", "dark_grey") + "  (no extra scopes beyond base)")
    else:
        # Show only selected commands
        for cmd, scopes in selected_command_scopes.items():
            if scopes:
                print(colored(f"  [{cmd}]", "yellow") + colored("  +extra", "dark_grey"))
                for s in scopes:
                    print(f"    {s}")
            else:
                print(colored(f"  [{cmd}]", "dark_grey") + "  (no extra scopes beyond base)")

    if unknown:
        print(colored(f"\n  Unknown commands (ignored): {', '.join(unknown)}", "red"))

    print()
    if summarising_all:
        print(colored(f"  Resolved (base only, no commands selected): {len(base)} scopes", "green"))
    else:
        print(colored(f"  Resolved total: {len(resolved)} scopes", "green"))
        for s in resolved:
            print(f"    {s}")

    return 0
