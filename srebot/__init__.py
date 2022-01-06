import click
from pathlib import Path
from .config import pass_config

global_data = {
    'config': None
}

@click.group()
@click.option("-l", "--log-level", type=click.Choice(['debug', 'info', 'warn', 'error'], case_sensitive=False))
@click.option("-c", "--config-file")
@pass_config
def cli(config, config_file, log_level):
    global_data['config'] = config
    if config_file:
        config.config_file = Path(config_file)

from . import bot