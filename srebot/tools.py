import os
import arrow
import hashlib
import time
import inquirer
import click
import sys
import subprocess
from pathlib import Path
from collections import namedtuple
from importlib import import_module
from contextlib import contextmanager
import importlib.util

PROC = namedtuple("Process", field_names=("process", "path", "md5"))

def _get_md5(filepath):
    if not filepath.exists():
        return ''
    m = hashlib.md5()
    m.update(filepath.read_bytes())
    return m.hexdigest()

def _raise_error(msg):
    click.secho(msg, fg='red')
    sys.exit(-1)

def _get_bots_paths(config):
    bots_paths = []

    for path in config.config.get('bots-paths', []):
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

def _get_robot_file(config, name):
    if name and name.startswith("/") or name.startswith("./"):
        name = Path(name).absolute()
    if not name:
        scripts = list(sorted(set(iterate_scripts(config))))
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

def kill_proc(proc, timeout):
    from . import global_data
    if not global_data['config']:
        return
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
    from . import global_data
    timeout_sec = 1
    if not global_data['config']:
        return
    for p in global_data['config'].processes:
        kill_proc(p, timeout_sec)

def cleanup():
    kill_all_processes()

def _select_bot_path():
    from . import global_data
    config = global_data['config']
    if not config.config.get('bots-paths'):
        _raise_error(f"Please configure a path in {config.config_file}")
    if len(config.config.get('bots-paths')) == 1:
        return config.config.get('bots-paths')[0]
    questions = [
        inquirer.List(name='path', message="Path", choices=sorted(config.config['bots-paths'])),
    ]
    answer = inquirer.prompt(questions)
    if not answer:
        return
    path = answer['path']
    return path

def load_module(path):
    mod_name = path.name.rsplit(".", 1)[0]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)
    return foo

@contextmanager
def _onetime_client(name_appendix, script, timeout=10):
    from .mqtt_tools import _get_regular_client
    from .mqtt_tools import _connect_client
    data = {'stop': False}
    def on_publish(client, userdata, mid):
        data['stop'] = True

    client = _get_regular_client(name=name_appendix, scriptfile=script)
    client.on_publish = on_publish
    _connect_client(client)
    yield client
    timeout = arrow.get().shift(seconds=timeout)
    while not data['stop'] and arrow.get() < timeout:
        client.loop(0.1)
    client.disconnect()