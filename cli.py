import json
import os
from time import sleep
import webbrowser
import shutil

import click
import requests
from termcolor import colored


from pysrc.utils.summarize_response import summarize_response
from pysrc.call_route import call_route

from pysrc.cli_routes.outlook.login import impl_outlook_login
from pysrc.cli_routes.outlook.me import impl_outlook_me
from pysrc.cli_routes.outlook.folders import impl_outlook_folders
from pysrc.cli_routes.outlook.index import impl_outlook_index
from pysrc.cli_routes.outlook.download import impl_outlook_download
from pysrc.cli_routes.outlook.safe_delete import impl_outlook_safe_delete



@click.group()
def cli():
    pass


@cli.group("outlook")
def outlook():
    pass


@outlook.command("login")
def outlook_login():
    return impl_outlook_login()


@outlook.command("me")
def outlook_me():
    return impl_outlook_me()

@outlook.command("folders")
def outlook_folders():
    return impl_outlook_folders()



@outlook.command("index")
@click.option("--reset", is_flag=True, default=False, help="Reset the index.")
def outlook_index(reset=False):
    return impl_outlook_index(reset)


@outlook.command("download")
def outlook_download():
    return impl_outlook_download()


@outlook.command("safe-delete")
@click.option(
    "--exact-sender",
    required=True,
    help="Exact sender email address to match.",
)
@click.option(
    "--exact-subject",
    required=True,
    help="Exact subject line to match.",
)
@click.option(
    "--case-sensitive",
    "--case-sensistive",
    is_flag=True,
    default=False,
    help="Match sender and subject case-sensitively.",
)
@click.option(
    "--preview-count",
    "--pc",
    default=25,
    type=int,
    show_default=True,
    help="Number of preview lines to show before confirming.",
)
@click.option(
    "--soft",
    is_flag=True,
    default=False,
    help="Move messages to trash instead of permanent delete.",
)
def outlook_safe_delete(
    exact_sender,
    exact_subject,
    case_sensitive=False,
    preview_count=25,
    soft=False,
):
    return impl_outlook_safe_delete(
        exact_sender=exact_sender,
        exact_subject=exact_subject,
        case_sensitive=case_sensitive,
        preview_count=preview_count,
        soft=soft,
    )

if __name__ == "__main__":
    cli()
