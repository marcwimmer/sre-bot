#!/usr/bin/env python3
import traceback
import arrow
import stat
import uuid
import signal
import time
import paho.mqtt.client as mqtt
import argparse
import inquirer
import sys
from pathlib import Path
from importlib import import_module
import os
import croniter
import importlib.util
import subprocess
import logging
import json
import textwrap
from collections import namedtuple
import hashlib
from datetime import datetime
import threading
import socket
import click
from . import cli
from .config import pass_config


VERSION = '0.1'

PROC = namedtuple("Process", field_names=("process", "path", "md5"))
global_data = {
    'config': None,
}

def _raise_error(msg):
    click.secho(msg, fg='red')
    sys.exit(-1)

@click.group()
@click.option("-l", "--log-level", type=click.Choice(['debug', 'info', 'warn', 'error'], case_sensitive=False))
def cli(log_level):
    pass

@cli.command(name='new')
@click.argument("name", required=True)
@pass_config
def make_new_file(config, name):
    questions = [
        inquirer.List(name='path', message="Path", choices=global_data['config'].config['bots-paths']),
    ]
    answer = inquirer.prompt(questions)
    path = answer['path']
    if not path:
        return
    for c in " ":
        name = name.replace(c, "_")
    dest_path = Path(path) / (name + ".py")
    if dest_path.exists():
        _raise_error(f"Already exists: {dest_path}")
    template = (config.current_dir / 'install' / 'bot.template.py').read_text()
    dest_path.write_text(template)

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

@cli.command()
@click.argument("name")
@pass_config
def make_install(config, name):
    config = global_data['config']

    # rewrite using virtual env
    for script_path in iterate_scripts(config):
        req_file = script_path.parent / 'requirements.txt'
        if req_file.exists():
            subprocess.check_call(["pip3", "install", '-r', req_file])
        mod = load_module(script_path)
        if getattr(mod, 'install', None):
            mod.install()

    name = 'autobot.service'
    install_systemd(name)

    paths = ', '.join(config['bots-paths'])
    click.secho(f"Add custom bots in {paths} using autobot.py --new ....", fg='yellow')
    click.secho(f"I setup following name: {config['name']}.")
    click.secho(f"{config.config_file}:")
    click.secho(config.config_file.read_text())

@cli.command()
@pass_config
def list_bots(config):
    for script in iterate_scripts(config):
        click.secho(script, fg='green')

def _get_md5(filepath):
    if not filepath.exists():
        return ''
    m = hashlib.md5()
    m.update(filepath.read_bytes())
    return m.hexdigest()

def start_proc(config, path):
    config.logger.info(f"Starting {path}...")
    path = path.absolute()

    os.system(f"pkill -9 -f '{path}'")

    process = subprocess.Popen([
        sys.executable,
        config.current_dir / 'autobot.py',
        'run',
        '-s', path,
        '-l', config.log_level,
    ])
    md5 = _get_md5(path)
    config = global_data['config']
    config.processes.append(PROC(process=process, path=path, md5=md5))

def _get_bots_paths(config):
    bots_paths = [
    ]

    for path in config.get('bots-paths', []):
        if not path: continue
        path = Path(path)
        for path in path.glob("**/*.py"):
            if '.git' in path.parts:
                continue
            if path.name.startswith("__"): continue
            if path.name.endswith(".py"):
                bots_paths.append(path.parent)

    for path in bots_paths:
        if path not in sys.path:
            sys.path += [path]
    return bots_paths

def iterate_scripts(config):
    result = set()

    def _collect():
        for bots_path in _get_bots_paths(config):
            for script in bots_path.glob("*.py"):
                if script.name.startswith("__"):
                    continue
                yield script
    for x in _collect():
        result.add(x)
    return sorted(list(result))


class mqttwrapper(object):
    def __init__(self, client, hostname, modulename):
        self.client = client
        self.hostname = hostname
        self.logger = global_data['config'].logger
        self.modulename = modulename

    def publish(self, path, payload=None, qos=0, retain=False):
        path = self.hostname + '/' + path
        value = {
            'module': self.modulename,
            'value': payload,
            # cannot use msg.timestamp - they use time.monotonic() which results
            # in consecutive calls results starting from 1970
            'timestamp': str(arrow.get().to('utc')),
        }
        self.client.publish(
            path,
            payload=json.dumps(value),
            qos=qos,
            retain=retain
        )

def _get_mqtt_wrapper(client, module):
    _name = getattr(module, "HOSTNAME", name) if module else name
    _modulename = Path(module.__file__).stem
    return mqttwrapper(client, _name, _modulename)

def on_connect(client, userdata, flags, reason, properties):
    global_data['config'].logger.debug(f"Client connected")
    client.subscribe("#")

def load_module(path):
    mod_name = path.name.rsplit(".", 1)[0]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)
    return foo

def on_message(client, userdata, msg):
    config = global_data['config']
    config.logger.debug(f"on_message: {msg.topic} {str(msg.payload)}")
    for script in iterate_scripts(config):
        module = load_module(script)
        if getattr(module, 'on_message', None):
            try:
                client2 = _get_mqtt_wrapper(client, module)
                try:
                    value = json.loads(msg.payload)
                except Exception:
                    # default values
                    value = {
                        'value': msg.payload,
                        'timestamp': str(arrow.get().to('utc')),
                        'module': None,
                    }
                module.on_message(client2, msg, value)

            except Exception as ex:
                _raise_error(str(traceback.format_exc()) + '\n\n' + str(ex))


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
            config.error(ex)
            time.sleep(1)

def _get_regular_client(name, scriptfile):
    client = mqtt.Client(client_id=f"autobot-{name}-{scriptfile.name})", protocol=mqtt.MQTTv5)
    return client

def _connect_client(client):
    config = global_data['config']
    client.connect(config.config['broker']['ip'], config.config['broker'].get('port', 1883), 60)

def run_single_robot(config, script):
    config.info(f"Starting script at {script}")
    script = Path(script).absolute()
    module = load_module(script)
    if not getattr(module, 'SCHEDULERS', None):
        return

    config.config['script_file'] = script
    client = _get_regular_client(config.config['name'], script)
    client.on_connect = on_connect
    client.on_message = on_message

    config.logger.info(f"Connecting to {config['broker']}")
    _connect_client(client)

    for scheduler in module.SCHEDULERS:
        t = threading.Thread(target=run_iter, args=(config, client, scheduler, module))
        t.daemon = False
        t.start()
    client.loop_forever()


def kill_proc(proc, timeout):
    p_sec = 0
    for second in range(timeout):
        if proc.process.poll() is None:
            time.sleep(0.1)
            p_sec += 1
    if p_sec >= timeout:
        proc.process.kill() # supported from python 2.6
    config = global_data['config']
    config.processes.pop(config.processes.index(proc))

def kill_all_processes():
    timeout_sec = 1
    for p in global_data['config'].processes:
        kill_proc(p, timeout_sec)

def cleanup():
    kill_all_processes()

class PseudoClient(object):
    def __init__(self):
        pass

    def publish(self, path, payload=None, qos=0):
        print(f"{path}:{qos}: {payload}")

def _get_robot_file(config, name):
    if name and name.startswith("/") or name.startswith("./"):
        name = Path(name).absolute()
    if not name:
        scripts = list(set(iterate_scripts(config)))
        questions = [
            inquirer.List('file', choices=scripts)
        ]
        answer = inquirer.prompt(questions)
        if not answer['file']:
            _raise_error("No file selected")
        return answer['file']

    filtered = list(filter(lambda x: name in x.name, iterate_scripts(config)))
    if len(filtered) > 1:
        _raise_error(f"Too many bots found for {name}")
        return
    if not filtered:
        _raise_error(f"No bot found for {name}")
        return
    return filtered[0].absolute()

# @cli.command()
# @click.argument("name", help="Name of script within search directories")
# @pass_config
# def test_bot(config, name):
#     name = _get_robot_file(config, name)

#     mod = load_module(name)
#     mod.run(PseudoClient())

# @cli.command()
# @click.argument("name", help="Name of script within search directories")
# @pass_config
# def run_once(config, name):
#     name = _get_robot_file(config, name)
#     mod = load_module(name)
#     config.config['script_file'] = name
#     reg_client = _get_regular_client(config.config['name'], name)
#     _connect_client(reg_client)
#     client = _get_mqtt_wrapper(reg_client, mod)
#     reg_client.loop_start()
#     mod.run(client)
#     print("Running mqtt for 10 seconds to publish items")
#     time.sleep(10)
#     reg_client.disconnect()
#     reg_client.loop_stop()

@cli.command()
@pass_config
def pull_bots(config):
    for script in iterate_scripts(config):
        git_dir = script.parent / '.git'
        if git_dir.exists():
            print(f"Executing git pull in {git_dir.parent}")
            subprocess.call(['git', 'pull'])

@cli.command()
@click.argument('script', required=False)
@pass_config
def run(config, script):
    if script:
        run_single_robot(script)
        return

    global_data['config'] = config

    while True:
        for proc in config.processes:
            if _get_md5(proc.path) != proc.md5:
                config.logger.info(f"Script was changed, restarting: {proc.path}")
                kill_proc(proc, 1)
                start_proc(proc.path)

        for script in iterate_scripts(config):
            if not [x for x in config.processes if x.path == script]:
                config.logger.info(f"Detected new script: {script}")
                start_proc(script)

        for proc in config.processes:
            if not [x for x in list(iterate_scripts(config)) if x == proc.path]:
                config.logger.info(f"Detected removal of script: {script}")
                kill_proc(proc, 1)

        time.sleep(2)