import os
from . import global_data
from pathlib import Path
import click
import sys
import subprocess

def install_systemd(name):
    config = global_data['config']
    for path in os.getenv("PATH").split(":"):
        if (Path(path) / "systemctl").exists():
            subprocess.call(["systemctl", "stop", name])
            template = (config.current_dir / '..' / name).read_text()

            # get python environment and executable
            exe = sys.executable + " " + sys.argv[0]
            template = template.replace('__path__', exe)
            template = template.replace('__config_file__', str(config.config_file))
            path = (Path("/etc/systemd/system/") / name)
            path.write_text(template)
            click.secho(path, fg='yellow')
            subprocess.check_call(["/bin/systemctl", "daemon-reload"])
            subprocess.check_call(["/bin/systemctl", "enable", name])
            subprocess.check_call(["/bin/systemctl", "restart", name])
            click.secho("Successfully installed with systemd.", fg='green')
            click.secho("Start the autobot with:", fg='yellow')
            click.secho(f'systemctl start {name}\n\n', fg='yellow')
            return True
