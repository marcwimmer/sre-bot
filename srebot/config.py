import atexit
import click
import logging
from pathlib import Path
import sys
from .tools import _raise_error, cleanup
import json
import socket

class Config(object):
    def __init__(self, config_file=None):
        super().__init__()
        self.config_file = Path(config_file or '/etc/sre/sre.conf')
        self.current_dir = Path(sys.path[0])
        self.processes = []
        self.load_config()
        self.setup_logging()
        self.bot = False
        atexit.register(cleanup)

    def setup_logging(self):
        log_level = (self.config.get('log_level') or 'INFO').upper()
        FORMAT = '[%(levelname)s] %(asctime)s %(message)s'
        formatter = logging.Formatter(FORMAT)
        logging.basicConfig(format=FORMAT)
        self.logger = logging.getLogger('')  # root handler
        self.logger.setLevel(log_level)

        if self.config.get('log_file'):
            log_file = Path(self.config.get('log_file'))
            log_file.parent.mkdir(exist_ok=True, parents=True)
            output_file_handler = logging.FileHandler(log_file)
            output_file_handler.setFormatter(formatter)
            self.logger.addHandler(output_file_handler)
            del log_file

        stdout_handler = logging.StreamHandler(sys.stdout)
        self.logger.addHandler(stdout_handler)
        stdout_handler.setFormatter(formatter)

    def store_config(self):
        self.config_file.write_text(
            json.dumps(self.config,
            indent=4)
        )

    def load_config(self):
        if self.config_file.exists():
            try:
                config = json.loads(self.config_file.read_text())
            except Exception as ex:
                _raise_error(f"config file corrupt:\n\n{ex}\n\n" + self.config_file.read_text())
        else: config = {}

        self._set_default_values(config)
        self.config = config

    def _set_default_values(self, config):
        config.setdefault('bots-paths', [])
        config.setdefault('name', socket.gethostname())
        config.setdefault('log_level', 'info')
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(config, indent=4))


pass_config = click.make_pass_decorator(Config, ensure=True)
