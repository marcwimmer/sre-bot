import os
from . import global_data
from pathlib import Path
import click
import sys
import subprocess
from importlib import import_module
import importlib.util

def _get_exe(config, path_to_sre):
    # get python environment and executable
    options = f" --config-file '{config.config_file}' daemon"
    if os.getenv("VIRTUAL_ENV"):
        ExecStart = f"/bin/sh -c 'cd \\'{os.getenv('VIRTUAL_ENV')}\\' && . bin/activate && python3 \\'{path_to_sre}\\' {options}'"
    else:
        ExecStart = f"'{sys.executable}' '{path_to_sre}' {options}"
    return ExecStart

def install_systemd(name, path_to_sre):
    config = global_data['config']
    subprocess.call(["systemctl", "stop", name])
    import srebot
    template = (Path(srebot.__file__).parent / 'datafiles' / 'sre.service').read_text()
    ExecStart = _get_exe(config, path_to_sre)

    template = template.replace('__exec_start__', ExecStart)
    template = template.replace('__name__', name)
    path = (Path("/etc/systemd/system/") / name)
    if path.exists():
        click.secho(f"Overwrite existing daemon file: {path}", fg='red')
    path.write_text(template)
    subprocess.check_call(["/bin/systemctl", "daemon-reload"])
    subprocess.check_call(["/bin/systemctl", "enable", name])
    subprocess.check_call(["/bin/systemctl", "restart", name])
    click.secho(f"Successfully installed with systemd: {name}", fg='green')

def install_requirements(path_to_sre):
    # rewrite using virtual env
    from . import global_data
    from .tools import iterate_scripts
    from .tools import load_module
    config = global_data['config']
    for script_path in iterate_scripts(config):
        req_file = script_path.parent / 'requirements.txt'
        if req_file.exists():
            _get_exe(config, path_to_sre, 'pip')
            subprocess.check_call(["pip", "install", '-r', req_file])
        mod = load_module(script_path)
        if getattr(mod, 'install', None):
            click.secho(f"Installing {mod.__file__}", fg='green')
            mod.install()
