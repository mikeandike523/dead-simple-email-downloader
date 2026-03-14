import os
import shutil
import socket
import subprocess
import sys
import webbrowser

import click
from termcolor import colored

from pysrc.utils.docker_ports import get_compose_port


def _split_commands(ctx, param, values):
    """Allow comma-separated values in addition to repeated flags.
    -c manage,download  →  ("manage", "download")
    -c manage -c download  →  ("manage", "download")
    """
    return tuple(cmd.strip() for v in values for cmd in v.split(",") if cmd.strip())

# ---------------------------------------------------------------------------
# Command implementations (exchange/outlook)
# ---------------------------------------------------------------------------
from pysrc.cli_routes.exchange.outlook.login import impl_exchange_outlook_login
from pysrc.cli_routes.exchange.outlook.logout import impl_exchange_outlook_logout
from pysrc.cli_routes.exchange.outlook.me import impl_exchange_outlook_me
from pysrc.cli_routes.exchange.outlook.folders import impl_exchange_outlook_folders
from pysrc.cli_routes.exchange.outlook.index import impl_exchange_outlook_index
from pysrc.cli_routes.exchange.outlook.download import impl_exchange_outlook_download
from pysrc.cli_routes.exchange.outlook.output import impl_exchange_outlook_output
from pysrc.cli_routes.exchange.outlook.safe_delete import impl_exchange_outlook_safe_delete
from pysrc.cli_routes.exchange.outlook.total_emails import impl_exchange_outlook_total_emails
from pysrc.cli_routes.exchange.outlook.debug_download import impl_exchange_outlook_debug_download

# ---------------------------------------------------------------------------
# Command implementations (google/gmail)
# ---------------------------------------------------------------------------
from pysrc.cli_routes.google.gmail.login import impl_google_gmail_login
from pysrc.cli_routes.google.gmail.logout import impl_google_gmail_logout
from pysrc.cli_routes.google.gmail.me import impl_google_gmail_me
from pysrc.cli_routes.google.gmail.folders import impl_google_gmail_folders
from pysrc.cli_routes.google.gmail.manage import impl_google_gmail_manage

# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
def cli():
    pass


# ---------------------------------------------------------------------------
# dsed exchange
# ---------------------------------------------------------------------------

@cli.group("exchange")
def exchange():
    """Microsoft Exchange / Microsoft 365 provider."""
    pass


# dsed exchange outlook
@exchange.group("outlook")
def exchange_outlook():
    """Outlook mail product (Exchange provider)."""
    pass


@exchange_outlook.command("login")
@click.option("-c", "--for-commands", "for_commands", multiple=True, metavar="CMD",
              callback=_split_commands, is_eager=False,
              help="Scopes for these commands (-c safe-delete or -c safe-delete,download).")
@click.option("--summarize-scopes", "summarize_scopes", is_flag=True, default=False,
              help="Print scopes that would be requested (all commands if none specified) and exit.")
def exchange_outlook_login(for_commands, summarize_scopes):
    """Authenticate with Microsoft and request Outlook scopes.

    By default only base scopes are requested (read-only).  Use -c to add
    the extra scopes a specific command needs:

    \b
      dsed exchange outlook login                        # base scopes only
      dsed exchange outlook login -c safe-delete         # + write scopes
      dsed exchange outlook login -c safe-delete,download
      dsed exchange outlook login -c safe-delete -c download

    To inspect what scopes would be requested without starting a login:

    \b
      dsed exchange outlook login --summarize-scopes              # show all
      dsed exchange outlook login -c safe-delete --summarize-scopes
    """
    return impl_exchange_outlook_login(for_commands=for_commands, summarize_scopes=summarize_scopes)


@exchange_outlook.command("logout")
def exchange_outlook_logout():
    """Clear server tokens and local JWT for the Exchange provider."""
    return impl_exchange_outlook_logout()


@exchange_outlook.command("me")
def exchange_outlook_me():
    """Print the authenticated user's Microsoft profile."""
    return impl_exchange_outlook_me()


@exchange_outlook.command("folders")
def exchange_outlook_folders():
    """List all mail folders."""
    return impl_exchange_outlook_folders()


@exchange_outlook.command("index")
@click.option("--reset", is_flag=True, default=False, help="Reset the index.")
def exchange_outlook_index(reset=False):
    """Build or update the local message index."""
    return impl_exchange_outlook_index(reset)


@exchange_outlook.command("download")
@click.option("--reset", is_flag=True, default=False, help="Delete caches before downloading.")
def exchange_outlook_download(reset=False):
    """Download full message content for all indexed messages."""
    return impl_exchange_outlook_download(reset)


@exchange_outlook.command("output")
@click.argument("outdir")
@click.option(
    "--max-subject-chars",
    type=click.IntRange(min=1),
    default=36,
    show_default=True,
    help="Maximum subject length to include in output folder names.",
)
def exchange_outlook_output(outdir, max_subject_chars=36):
    """Export downloaded messages to a human-readable directory."""
    return impl_exchange_outlook_output(outdir, max_subject_chars=max_subject_chars)


@exchange_outlook.command("debug-download")
@click.argument("features", nargs=-1)
@click.option(
    "--index",
    "build_index",
    is_flag=True,
    default=False,
    help="Build the debug index and exit.",
)
def exchange_outlook_debug_download(features, build_index=False):
    """Open a random cached message matching the requested features."""
    return impl_exchange_outlook_debug_download(features, build_index)


@exchange_outlook.command("total-emails")
def exchange_outlook_total_emails():
    """Print total email counts per folder."""
    return impl_exchange_outlook_total_emails()


@exchange_outlook.command("safe-delete")
@click.option("--exact-sender", help="Exact sender email address to match.")
@click.option("--exact-subject", help="Exact subject line to match.")
@click.option("--regex", is_flag=True, default=False, help="Treat the subject as a regex pattern.")
@click.option("--prompt", is_flag=True, default=False, help="Prompt for sender and subject.")
@click.option("--case-sensitive", "--case-sensistive", is_flag=True, default=False)
@click.option("--preview-count", "--pc", default=25, type=int, show_default=True)
@click.option("--all", "show_all", is_flag=True, default=False)
@click.option("--report", is_flag=True, default=False, help="Print previews only, skip deletion.")
@click.option("-y", "--yes", "assume_yes", is_flag=True, default=False)
@click.option("--soft", is_flag=True, default=False, help="Move to trash instead of permanent delete.")
def exchange_outlook_safe_delete(
    exact_sender, exact_subject, regex=False, prompt=False,
    case_sensitive=False, preview_count=25, show_all=False,
    report=False, assume_yes=False, soft=False,
):
    """Find and delete messages matching sender/subject criteria."""
    return impl_exchange_outlook_safe_delete(
        exact_sender=exact_sender,
        exact_subject=exact_subject,
        subject_is_regex=regex,
        prompt=prompt,
        case_sensitive=case_sensitive,
        preview_count=preview_count,
        show_all=show_all,
        report=report,
        assume_yes=assume_yes,
        soft=soft,
    )


# ---------------------------------------------------------------------------
# dsed google
# ---------------------------------------------------------------------------

@cli.group("google")
def google():
    """Google Cloud provider."""
    pass


# dsed google gmail
@google.group("gmail")
def google_gmail():
    """Gmail product (Google provider)."""
    pass


@google_gmail.command("login")
@click.option("-c", "--for-commands", "for_commands", multiple=True, metavar="CMD",
              callback=_split_commands, is_eager=False,
              help="Scopes for these commands (-c manage or -c manage,download).")
@click.option("--summarize-scopes", "summarize_scopes", is_flag=True, default=False,
              help="Print scopes that would be requested (all commands if none specified) and exit.")
def google_gmail_login(for_commands, summarize_scopes):
    """Authenticate with Google and request Gmail scopes.

    By default only base scopes are requested (read-only).  Use -c to add
    the extra scopes a specific command needs:

    \b
      dsed google gmail login                  # base scopes only
      dsed google gmail login -c manage        # + gmail.modify
      dsed google gmail login -c manage,download
      dsed google gmail login -c manage -c download

    To inspect what scopes would be requested without starting a login:

    \b
      dsed google gmail login --summarize-scopes           # show all
      dsed google gmail login -c manage --summarize-scopes
    """
    return impl_google_gmail_login(for_commands=for_commands, summarize_scopes=summarize_scopes)


@google_gmail.command("logout")
def google_gmail_logout():
    """Clear server tokens and local JWT for the Google provider."""
    return impl_google_gmail_logout()


@google_gmail.command("me")
def google_gmail_me():
    """Print the authenticated user's Google profile."""
    return impl_google_gmail_me()


@google_gmail.command("folders")
def google_gmail_folders():
    """List Gmail labels with total, unread, and read message counts."""
    return impl_google_gmail_folders()


@google_gmail.command("manage")
@click.option(
    "--force-label-case",
    "force_label_case",
    is_flag=True,
    default=False,
    help="Require exact label casing instead of case-insensitive matching.",
)
def google_gmail_manage(force_label_case):
    """Open the interactive inbox triage TUI.

    Triage emails one at a time: categorize for ML training, skip, move,
    or delete.  Requires login with -c manage scope:

    \b
      dsed google gmail login -c manage
      dsed google gmail manage

    Commands inside the TUI:

    \b
      cat <category>                  assign a category, advance
      hard-delete                     permanently delete, advance
      soft-delete                     move to Trash, advance
      move <label>                    move to Gmail label, advance
      cat <category> hard-delete      assign + delete
      cat <category> soft-delete      assign + trash
      cat <category> move <label>     assign + move
      (empty) / skip                  skip, advance

    If a label typed in move commands is ambiguous due to case conflicts,
    re-run with --force-label-case to require exact casing.
    """
    return impl_google_gmail_manage(force_label_case=force_label_case)


# ---------------------------------------------------------------------------
# dsed phpmyadmin
# ---------------------------------------------------------------------------

@cli.command("phpmyadmin")
def phpmyadmin():
    """Open phpMyAdmin in a browser (or print its URL when piped)."""
    port = get_compose_port("phpmyadmin", 80)
    url = f"http://localhost:{port}"
    if sys.stdout.isatty():
        click.echo(url)
        webbrowser.open(url, new=0)
    else:
        sys.stdout.write(url)


# ---------------------------------------------------------------------------
# dsed backend
# ---------------------------------------------------------------------------

@cli.group("backend")
def backend():
    """Backend server management."""
    pass


@backend.command("start")
@click.option("--port", type=int, default=None, help="Use a fixed port (e.g. 3000 for OAuth redirect URL compatibility).")
def backend_start(port):
    """Find a free port and start the Next.js backend (blocking)."""
    if port is not None:
        next_port = port
    else:
        # Find a free port for Next.js
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            next_port = s.getsockname()[1]

    # Persist port so the Python CLI can discover it
    runtime_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runtime")
    os.makedirs(runtime_dir, exist_ok=True)
    runtime_file = os.path.join(runtime_dir, "next_port.txt")
    with open(runtime_file, "w", encoding="utf-8") as f:
        f.write(str(next_port))

    # Discover MySQL host port
    mysql_port = get_compose_port("db", 3306)

    click.echo(colored(f"{'Using fixed port' if port is not None else 'Found random open port'}: {next_port}", "cyan"))
    click.echo(colored(f"MySQL mapped to host port: {mysql_port}", "cyan"))
    click.echo(colored(f"Backend listening on http://localhost:{next_port}", "green"))

    env = os.environ.copy()
    env["PORT"] = str(next_port)
    env["MYSQL_PORT"] = str(mysql_port)

    pnpm = shutil.which("pnpm")
    if not pnpm:
        click.echo(colored("Error: pnpm not found on PATH.", "red"))
        sys.exit(1)

    try:
        subprocess.run([pnpm, "start"], env=env, cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
