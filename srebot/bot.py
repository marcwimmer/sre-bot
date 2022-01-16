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
from .webserver import start_webserver
from .tools import _onetime_client


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
    import srebot
    template = (Path(srebot.__file__).parent / 'datafiles' / 'bot.template.py').read_text()
    dest_path.write_text(template)
    click.secho(f"Created new bot in {dest_path}", fg='green')

@cli.command(name="install", help="Installs all new requirements of bots and installs as a system service.")
@click.option("-n", "--name", required=False, default='sre')
@pass_config
def make_install(config, name):
    from . install_services import install_systemd
    from . install_services import install_requirements
    config = global_data['config']

    install_requirements(sys.argv[0])
    if not name.endswith('.service'):
        name = name + ".service"
    install_systemd(name, sys.argv[0])

    paths = ', '.join(config.config['bots-paths'])
    click.secho(f"Add custom bots: {name} new bot1", fg='yellow')
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
    os.system(f"pkill -9 -f '{sys.executable} .*{path}'")

    process = subprocess.Popen([
        sys.executable,
        sys.argv[0],
        '-c', config.config_file,
        '-l', config.config.get('log_level'),
        'run',
        path,
    ])
    md5 = _get_md5(path)
    config = global_data['config']
    config.processes.append(PROC(process=process, path=path, md5=md5))

def run_iter(config, client, scheduler, module, once):
    from . import global_data
    global_data['config'] = config
    base = datetime.now()
    iter = croniter.croniter(scheduler, base)
    while True:
        try:
            next = iter.get_next(datetime)
            config.logger.debug(f"Executing {module} next at {next.strftime('%Y-%m-%d %H:%M:%S')}")

            while True:
                if datetime.now() > next or once:

                    client2 = _get_mqtt_wrapper(client, module)
                    script_file = config.bot
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
            msg = traceback.format_exc()
            config.logger.error(msg)
            time.sleep(1)
        finally:
            if once:
                return

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
    path = path.strip()
    path = Path(path).absolute()
    path.mkdir(parents=True, exist_ok=True)
    if str(path) not in config.config['bots-paths']:
        config.config['bots-paths'].append(str(path))
    config.store_config()

@cli.command(help="Start main loop or sub daemon script (called by service usually)")
@click.option('-1', '--once', required=False, is_flag=True)
@click.argument('script', required=False)
@pass_config
def run(config, script, once):
    if not script:
        script = _get_robot_file(config, '')
    if not str(script).startswith('/'):
        script = Path(os.getcwd()) / script
        if not script.exists():
            _raise_error("Needs absolute path if killing existing script")

    #if kill_others:
    #    os.system(f"pkill -9 -f '{sys.executable}.*{sys.argv[0]}.*{script}'")
    script = Path(script).absolute()
    module = load_module(script)
    config.logger.info(f"Starting script at {script}")
    config.bot = script
    client = _get_regular_client(config.config['name'], script)
    client.on_connect = on_connect
    client.on_message = on_message

    config.logger.info(f"Connecting to {config.config['broker']}")

    while True:
        try:
            _connect_client(client)
        except Exception as ex:
            msg = traceback.format_exc()
            config.logger.error(msg)
            time.sleep(1)
        else:
            break

    for scheduler in getattr(module, 'SCHEDULERS', []):
        if once:
            with _onetime_client('_run_once', script) as client:
                os.environ["SRE_OUTPUT_MESSAGES"] = "1"
                run_iter(config, client, scheduler, module, once=True)
            return
        else:
            t = threading.Thread(target=run_iter, args=(config, client, scheduler, module, False))
            t.daemon = False
            t.start()
            t.join
    client.loop_forever()

@cli.command(help="Start main loop or sub daemon script (called by service usually)")
@pass_config
def daemon(config):
    config.logger.info("Starting daemon...")
    t = threading.Thread(target=start_webserver,)
    t.daemon = True
    t.start()

    while True:
        for proc in config.processes:
            if _get_md5(proc.path) != proc.md5:
                config.logger.info(f"Script was changed, restarting: {proc.path}")
                kill_proc(proc, 1)
                start_proc(config, proc.path)

        for script in iterate_scripts(config):
            if str(script) in config.config.get('disabled', []):
                continue
            if not [x for x in config.processes if x.path == script]:
                config.logger.info(f"Detected new script: {script}")
                start_proc(config, script)

        for proc in config.processes:
            if not [x for x in list(iterate_scripts(config)) if x == proc.path]:
                config.logger.info(f"Detected removal of script: {script}")
                kill_proc(proc, 1)

        time.sleep(2)

@cli.command(name="state")
@pass_config
def state(config):
    scripts = list(sorted(map(str, iterate_scripts(config))))
    defaults = []
    for script in scripts:
        script = script
        if script not in config.config.get('disabled', []):
            defaults.append(script)
    questions = [inquirer.Checkbox('state', message="Turn on bots", choices=scripts, default=defaults)]
    answer = inquirer.prompt(questions)
    if not answer:
        return

    disabled = []
    for script in scripts:
        if script not in answer['state']:
            disabled.append(script)
    config.config['disabled'] = disabled
    config.store_config()
    click.secho("Settings applied. Dont forget to restart the service.", fg='yellow')