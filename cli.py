import click
from termcolor import colored

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
# dsed outlook  (deprecated shims — kept for backward compatibility)
# ---------------------------------------------------------------------------

@cli.group("outlook")
def outlook():
    """Deprecated: use 'dsed exchange outlook <command>' instead."""
    pass


def _deprecation_warning(new_cmd: str):
    click.echo(
        colored(
            f"Warning: 'dsed outlook' is deprecated. Use 'dsed exchange outlook {new_cmd}' instead.",
            "yellow",
        ),
        err=True,
    )


@outlook.command("login")
def outlook_login():
    _deprecation_warning("login")
    return impl_exchange_outlook_login()


@outlook.command("logout")
def outlook_logout():
    _deprecation_warning("logout")
    return impl_exchange_outlook_logout()


@outlook.command("me")
def outlook_me():
    _deprecation_warning("me")
    return impl_exchange_outlook_me()


@outlook.command("folders")
def outlook_folders():
    _deprecation_warning("folders")
    return impl_exchange_outlook_folders()


@outlook.command("index")
@click.option("--reset", is_flag=True, default=False)
def outlook_index(reset=False):
    _deprecation_warning("index")
    return impl_exchange_outlook_index(reset)


@outlook.command("download")
@click.option("--reset", is_flag=True, default=False)
def outlook_download(reset=False):
    _deprecation_warning("download")
    return impl_exchange_outlook_download(reset)


@outlook.command("output")
@click.argument("outdir")
@click.option("--max-subject-chars", type=click.IntRange(min=1), default=36, show_default=True)
def outlook_output(outdir, max_subject_chars=36):
    _deprecation_warning("output")
    return impl_exchange_outlook_output(outdir, max_subject_chars=max_subject_chars)


@outlook.command("debug-download")
@click.argument("features", nargs=-1)
@click.option("--index", "build_index", is_flag=True, default=False)
def outlook_debug_download(features, build_index=False):
    _deprecation_warning("debug-download")
    return impl_exchange_outlook_debug_download(features, build_index)


@outlook.command("total-emails")
def outlook_total_emails():
    _deprecation_warning("total-emails")
    return impl_exchange_outlook_total_emails()


@outlook.command("safe-delete")
@click.option("--exact-sender")
@click.option("--exact-subject")
@click.option("--regex", is_flag=True, default=False)
@click.option("--prompt", is_flag=True, default=False)
@click.option("--case-sensitive", "--case-sensistive", is_flag=True, default=False)
@click.option("--preview-count", "--pc", default=25, type=int, show_default=True)
@click.option("--all", "show_all", is_flag=True, default=False)
@click.option("--report", is_flag=True, default=False)
@click.option("-y", "--yes", "assume_yes", is_flag=True, default=False)
@click.option("--soft", is_flag=True, default=False)
def outlook_safe_delete(
    exact_sender, exact_subject, regex=False, prompt=False,
    case_sensitive=False, preview_count=25, show_all=False,
    report=False, assume_yes=False, soft=False,
):
    _deprecation_warning("safe-delete")
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


if __name__ == "__main__":
    cli()
