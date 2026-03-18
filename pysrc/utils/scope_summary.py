"""
CLI helper: pretty-print scope breakdown from the Python scope registry.
No backend call required.
"""
from termcolor import colored

from pysrc.utils.scopes import describe_scope_request


def print_scope_summary(provider: str, product: str, commands: list[str]) -> int:
    """
    Pretty-print the scope breakdown for a given provider/product/command set.

    - No commands: shows base scopes + ALL known command scopes for reference.
    - Commands given: shows base + selected command scopes + what each adds.

    Returns 0 on success, -1 on failure.
    """
    d = describe_scope_request(provider, product, commands)

    base: list[str] = d["base"]
    all_command_scopes: dict = d["allCommandScopes"]
    selected_command_scopes: dict = d["selectedCommandScopes"]
    resolved: list[str] = d["resolved"]
    unknown: list[str] = d["unknownCommands"]

    if not base and not all_command_scopes:
        print(colored(f"Unknown provider/product: {provider}/{product}", "red"))
        return -1

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
        for cmd, scopes in all_command_scopes.items():
            if scopes:
                print(colored(f"  [{cmd}]", "yellow") + colored("  +extra", "dark_grey"))
                for s in scopes:
                    print(f"    {s}")
            else:
                print(colored(f"  [{cmd}]", "dark_grey") + "  (no extra scopes beyond base)")
    else:
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
