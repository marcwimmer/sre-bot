import os
from . import global_data
from pathlib import Path
import click
import sys
import subprocess
from importlib import import_module
import importlib.util

SRE_CONSOLE = "/usr/local/bin/sre-console"

def install_systemd(name):
    config = global_data['config']
    for path in os.getenv("PATH").split(":"):
        subprocess.call(["systemctl", "stop", name])
        template = (config.current_dir / '..' / 'sre-bots' / name).read_text()

        # get python environment and executable
        exe = f"'{sys.executable}' '{SRE_CONSOLE}'"
        template = template.replace('__path__', exe)
        template = template.replace('__config_file__', str(config.config_file))
        path = (Path("/etc/systemd/system/") / name)
        path.write_text(template)
        click.secho(str(path), fg='yellow')
        subprocess.check_call(["/bin/systemctl", "daemon-reload"])
        subprocess.check_call(["/bin/systemctl", "enable", name])
        subprocess.check_call(["/bin/systemctl", "restart", name])
        click.secho("Successfully installed with systemd.", fg='green')
        click.secho("Start the sre with:", fg='yellow')
        click.secho(f'systemctl start {name}\n\n', fg='yellow')
        return True

def install_requirements():
    # rewrite using virtual env
    from . import global_data
    from .tools import iterate_scripts
    from .tools import load_module
    config = global_data['config']
    for script_path in iterate_scripts(config):
        req_file = script_path.parent / 'requirements.txt'
        if req_file.exists():
            subprocess.check_call(["pip", "install", '-r', req_file])
        mod = load_module(script_path)
        if getattr(mod, 'install', None):
            mod.install()

def install_executable(name):
    from . import global_data
    bin_dir = Path("/usr/local/bin")
    if name != 'sre':
        name = 'sre.' + name
    path = bin_dir / name
    path.write_text("""#!/bin/bash
if [[ -z "$@" ]]; then
    set -- "--help"
fi
{exe} {SRE_CONSOLE} --config-file {config_file} "$@"
""".format(
        config_file=global_data['config'].config_file,
        exe=sys.executable,
        script=sys.argv[0],
        SRE_CONSOLE=SRE_CONSOLE,
    ))
    os.chmod(path, 0o555)
    click.secho(f"Installed new executable in {path}", fg='green')