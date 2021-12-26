import atexit
import click
import logging
from pathlib import Path

class Config(object):
    def __init__(self, log_level):
        super().__init__()

        print("""
        Easily runs observing scripts and publishes to mqtt. Receiving also possible.
        """)
        self.log_level = log_level or 'info'
        self.current_dir = Path(sys.path[0])
        self.load_config()
        self.processes = []
        atexit.register(cleanup)

    def setup_logging(self):
        FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
        logging.basicConfig(format=FORMAT)
        self.logger = logging.getLogger('')  # root handler
        self.logger.setLevel(self.log_level)

    def load_config(self):
        self.config_file = Path("/etc/sre/autobot.conf")
        if self.config_file.exists():
            try:
                config = json.loads(self.config_file.read_text())
            except Exception:
                _raise_error("config file corrupt:\n\n" + self.config_file.read_text())
        else: config = {}

        if not config.get('name'):
            self._set_default_values()
            self.load_config()
        self.config = config

    def _set_default_values(self):
        config = json.loads((self.current_dir / 'install' / 'autobot.conf').read_text())
        config.setdefault('bots-paths', [])
        config.setdefault('name', socket.gethostname())
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(config, indent=4))

pass_config = click.make_pass_decorator(Config, ensure=True)
