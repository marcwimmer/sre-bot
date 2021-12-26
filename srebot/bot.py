#!/usr/bin/env python3
import traceback
import arrow
import stat
import uuid
import signal
import time
import argparse
import inquirer
import sys
from pathlib import Path
import os
import croniter
import subprocess
import json
from datetime import datetime
import threading
import click
from . import cli
from .config import pass_config
from .mqtt_tools import PseudoClient
from .tools import _get_md5, _raise_error, PROC, iterate_scripts, _get_robot_file, kill_proc, _select_bot_path, load_module
from . import global_data
from . mqtt_tools import _get_mqtt_wrapper, _connect_client, _get_regular_client, on_connect, on_message


VERSION = '0.2'

@cli.command(name='new', help="Makes new bot from template")
@click.argument("name", required=True)
@pass_config
def make_new_file(config, name):
    path = _select_bot_path()
    if not path:
        return
    for c in " ":
        name = name.replace(c, "_")
    dest_path = Path(path) / (name + ".py")
    if dest_path.exists():
        _raise_error(f"Already exists: {dest_path}")
    template = (config.current_dir / '..' / 'bot.template.py').read_text()
    dest_path.write_text(template)
    click.secho(f"Created new bot in {dest_path}", fg='green')

@cli.command(name="install", help="Installs all new requirements of bots and installs as a system service.")
@click.option("-n", "--name", required=False, default='sre')
@pass_config
def make_install(config, name):
    from . install_services import install_systemd
    from . install_services import install_requirements
    from . install_services import install_executable
    config = global_data['config']

    install_requirements()
    install_executable(name)
    if not name.endswith('.service'):
        name = name + ".service"
    install_systemd(name)

    paths = ', '.join(config.config['bots-paths'])
    click.secho(f"Add custom bots in {paths} using: name new bot1", fg='yellow')
    click.secho(f"I setup following name: {name}.")
    click.secho(f"{config.config_file}:")
    click.secho(config.config_file.read_text())

@cli.command(name='list')
@pass_config
def list_bots(config):
    for script in iterate_scripts(config):
        click.secho(script, fg='green')

def start_proc(config, path):
    config.logger.info(f"Starting {path}...")
    path = path.absolute()

    os.system(f"pkill -9 -f '{path}'")

    process = subprocess.Popen([
        sys.executable,
        sys.argv[0],
        '-c', config.config_file,
        '-l', config.log_level,
        'run',
        path,
    ])
    md5 = _get_md5(path)
    config = global_data['config']
    config.processes.append(PROC(process=process, path=path, md5=md5))

def run_iter(config, client, scheduler, module):
    base = datetime.now()
    iter = croniter.croniter(scheduler, base)
    while True:
        try:
            next = iter.get_next(datetime)
            config.logger.debug(f"Executing {module} next at {next.strftime('%Y-%m-%d %H:%M:%S')}")

            while True:
                if datetime.now() > next:

                    client2 = _get_mqtt_wrapper(client, module)
                    script_file = config.config['script_file']
                    if getattr(module, 'run', None):
                        try:
                            config.logger.debug(f"Running {script_file}:run")
                            module.run(client2)
                            client2.publish(script_file.name + '/rc', payload=0)
                        except Exception as ex:
                            client2.publish(script_file.name + '/rc', payload=1)
                            client2.publish(script_file.name + '/last_error', payload=str(ex))
                            client2.publish('/last_error', payload=f"{script_file}\n{ex}")
                            config.logger.error(ex)
                            time.sleep(1)
                    break
                time.sleep(0.5)

        except Exception as ex:
            import traceback
            msg = traceback.format_exc()
            config.logger.error(msg)
            time.sleep(1)

@cli.command(help="Name of script within search directories")
@click.argument("name")
@pass_config
def test_bot(config, name):
    name = _get_robot_file(config, name)

    mod = load_module(name)
    mod.run(PseudoClient())

@cli.command()
@click.argument('path', type=click.Path(exists=False))
@pass_config
def add_bot_path(config, path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if path not in config.config['bots-paths']:
        config.config['bots-paths'].append(str(path))
    config.store_config()

@cli.command(help="Start main loop or sub daemon script (called by service usually)")
@click.option('-1', '--once', required=False, is_flag=True)
@click.argument('script', required=False)
@pass_config
def run(config, script, once):
    script = Path(script).absolute()
    module = load_module(script)
    if not getattr(module, 'SCHEDULERS', None):
        return
    config.logger.info(f"Starting script at {script}")
    config.config['script_file'] = script
    client = _get_regular_client(config.config['name'], script)
    client.on_connect = on_connect
    client.on_message = on_message

    config.logger.info(f"Connecting to {config.config['broker']}")
    _connect_client(client)

    for scheduler in module.SCHEDULERS:
        t = threading.Thread(target=run_iter, args=(config, client, scheduler, module))
        t.daemon = False
        t.start()
        if once:
            client.loop_start()
            t.join()
            client.loop_stop()
            client.disconnect()
            return
    client.loop_forever()

@cli.command(help="Start main loop or sub daemon script (called by service usually)")
@pass_config
def daemon(config):
    while True:
        for proc in config.processes:
            if _get_md5(proc.path) != proc.md5:
                config.logger.info(f"Script was changed, restarting: {proc.path}")
                kill_proc(proc, 1)
                start_proc(config, proc.path)

        for script in iterate_scripts(config):
            if not [x for x in config.processes if x.path == script]:
                config.logger.info(f"Detected new script: {script}")
                start_proc(config, script)

        for proc in config.processes:
            if not [x for x in list(iterate_scripts(config)) if x == proc.path]:
                config.logger.info(f"Detected removal of script: {script}")
                kill_proc(proc, 1)

        time.sleep(2)
