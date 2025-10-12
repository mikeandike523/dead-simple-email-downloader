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

if __name__ == "__main__":
    cli()
