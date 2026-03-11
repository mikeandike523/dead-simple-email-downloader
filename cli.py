import os
import socket
import subprocess
import sys
import webbrowser

import click
from termcolor import colored

from pysrc.utils.docker_ports import get_compose_port

# ---------------------------------------------------------------------------
# New command implementations (exchange/outlook)
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
def exchange_outlook_login():
    """Authenticate with Microsoft and request Outlook scopes."""
    return impl_exchange_outlook_login()


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
def backend_start():
    """Find a free port and start the Next.js backend (blocking)."""
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

    click.echo(colored(f"Found random open port: {next_port}", "cyan"))
    click.echo(colored(f"MySQL mapped to host port: {mysql_port}", "cyan"))
    click.echo(colored(f"Backend listening on http://localhost:{next_port}", "green"))

    env = os.environ.copy()
    env["PORT"] = str(next_port)
    env["MYSQL_PORT"] = str(mysql_port)

    try:
        subprocess.run(["pnpm", "start"], env=env)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
