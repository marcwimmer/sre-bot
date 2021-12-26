import hashlib
import time
import inquirer
import click
import sys
from pathlib import Path
from collections import namedtuple

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