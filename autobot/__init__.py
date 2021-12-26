import click
from .config import pass_config

global_data = {
    'config': None
}

@click.group()
@click.option("-l", "--log-level", type=click.Choice(['debug', 'info', 'warn', 'error'], case_sensitive=False, required=False, default='info'))
@pass_config
def cli(config, log_level):
    config.set_log_level(log_level)

from . import autobot