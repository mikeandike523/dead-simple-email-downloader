import click


@click.group()
def cli():
    pass

@cli.group("outlook")
def outlook():
    pass

@outlook.command("login")
def outlook_login():
    ...


if __name__ == '__main__':
    cli()