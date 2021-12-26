import click

@click.group()
@click.option("-l", "--log-level", type=click.Choice(['debug', 'info', 'warn', 'error'], case_sensitive=False))
def cli(log_level):
    pass

from . import autobot