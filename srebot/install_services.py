import os
from . import global_data
from pathlib import Path
import click
import sys
import subprocess
from importlib import import_module
import importlib.util

def install_systemd(name, path_to_sre):
    config = global_data['config']
    subprocess.call(["systemctl", "stop", name])
    template = (config.current_dir / '..' / 'sre-bots' / name).read_text()

    # get python environment and executable
    exe = f"'{sys.executable}' '{path_to_sre}'"
    template = template.replace('__path__', exe)
    template = template.replace('__name__', name)
    template = template.replace('__config_file__', str(config.config_file))
    path = (Path("/etc/systemd/system/") / name)
    if path.exists():
        click.secho(f"Overwrite existing daemon file: {path}", fg='red')
    path.write_text(template)
    subprocess.check_call(["/bin/systemctl", "daemon-reload"])
    subprocess.check_call(["/bin/systemctl", "enable", name])
    subprocess.check_call(["/bin/systemctl", "restart", name])
    click.secho(f"Successfully installed with systemd: {name}", fg='green')

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
