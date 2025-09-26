import click
import requests
from termcolor import colored


@click.group()
def cli():
    pass

@cli.group("outlook")
def outlook():
    pass

@outlook.command("login")
def outlook_login():
    response = requests.get("http://localhost:3000/api/auth/outlook/get-url")
    response.raise_for_status()
    authorize_url=response.json()
    print("Please open the following URL in your browser:")

    #print blue and underlined
    print(colored(authorize_url, 'blue', attrs=['underline']))

    # todo: poll for successful login on backend side...

if __name__ == '__main__':
    cli()