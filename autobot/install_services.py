from . import global_data
from pathlib import Path
import click
import subprocess

def install_systemd(name):
    config = global_data['config']
    for path in os.getenv("PATH").split(":"):
        if (Path(path) / "systemctl").exists():
            subprocess.call(["systemctl", "stop", name])
            template = (config.current_dir / 'install' / name).read_text()
            template = template.replace('__path__', str(config.current_dir / 'autobot.py'))
            (Path("/etc/systemd/system/") / name).write_text(template)
            subprocess.check_call(["/bin/systemctl", "daemon-reload"])
            subprocess.check_call(["/bin/systemctl", "enable", name])
            subprocess.check_call(["/bin/systemctl", "restart", name])
            click.secho("Successfully installed with systemd.", fg='green')
            click.secho("Start the autobot with:", fg='yellow')
            click.secho(f'systemctl start {name}\n\n', fg='yellow')
            return True
