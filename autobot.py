#!/usr/bin/env python3
import uuid
import atexit
import signal
import time
import paho.mqtt.client as mqtt
import argparse
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

config = json.loads(Path("/etc/sre/autobot.conf").read_text())


FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('')  # root handler
current_dir = Path(sys.path[0])

PROC = namedtuple("Process", field_names=("process", "path", "md5"))

parser = argparse.ArgumentParser(description='Bot SRE', epilog="""

Easily runs observing scripts and publishes to mqtt. Receiving also possible.

""")
parser.add_argument('-s', metavar="Script", type=str, required=False)
parser.add_argument('-l', metavar="Level", type=str, required=False, default='INFO')
parser.add_argument('-i', '--install', required=False, action='store_true')
parser.add_argument('-n', '--new', required=False)
args = parser.parse_args()

name = config['name']

logging.getLogger().setLevel(args.l.upper())

bots_paths = [
    Path(sys.path[0]) / 'bots.d',
    Path('/etc/sre/bots.d'),
]
sys.path += bots_paths

processes = []

if args.new:
    new_name = args.new
    for c in " ":
        new_name = new_name.replace(c, "_")
    dest_path = bots_paths[1] / (new_name + ".py")
    if dest_path.exists():
        print(f"Already exists: {dest_path}")
        sys.exit(-1)
    template = (current_dir / 'install' / 'bot.template.py').read_text()
    dest_path.write_text(template)


if args.install:
    name = 'autobot.service'
    template = (current_dir / 'install' / name).read_text()
    template = template.replace('__path__', str(Path(os.getcwd()) / 'autobot.py'))
    (Path("/etc/systemd/system/") / name).write_text(template)
    subprocess.check_call(["/usr/bin/systemctl", "enable", name])
    print(f'systemctl start {name}')
    sys.exit(0)

def _get_md5(filepath):
    if not filepath.exists():
        return ''
    m = hashlib.md5()
    m.update(filepath.read_bytes())
    return m.hexdigest()

def start_proc(path):
    process = subprocess.Popen([
        '/usr/bin/python3',
        'autobot.py',
        '-s', path,
        '-l', args.l,
    ])
    md5 = _get_md5(path)
    processes.append(PROC(process=process, path=path, md5=md5))

def iterate_scripts():
    for bots_path in bots_paths:
        for script in bots_path.glob("*.py"):
            if script.name.startswith("__"):
                continue
            yield script

def start_main():
    while True:
        for proc in processes:
            if _get_md5(proc.path) != proc.md5:
                kill_proc(proc, 1)
                start_proc(proc.path)

        for script in iterate_scripts():
            if not [x for x in processes if x.path == script]:
                start_proc(script)

        for proc in processes:
            if not [x for x in list(iterate_scripts()) if x == proc.path]:
                kill_proc(proc, 1)

        time.sleep(1)


class mqttwrapper(object):
    def __init__(self, client, hostname):
        self.client = client
        self.hostname = hostname
        self.logger = logger

    def publish(self, path, payload=None, qos=0, retain=False):
        path = self.hostname + '/' + path
        self.client.publish(
            path,
            payload=payload,
            qos=qos,
            retain=retain
        )

def on_connect(client, userdata, flags, reason, properties):
    logger.debug(f"Client connected {args.s}")
    client.subscribe("#")

def iterate_modules():
    file = Path(args.s)
    module = load_module(file)
    yield module

def load_module(path):
    mod_name = path.name.rsplit(".", 1)[0]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)
    return foo


def on_message(client, userdata, msg):
    logger.debug(f"on_message:{args.s}: {msg.topic} {str(msg.payload)}")
    client2 = mqttwrapper(client, name)
    for module in iterate_modules():
        if getattr(module, 'on_message', None):
            try:
                module.on_message(client2, userdata, msg)
            except Exception as ex:
                logger.error(ex)

def run_iter(client, scheduler, module):
    base = datetime.now()
    iter = croniter.croniter(scheduler, base)
    while True:
        try:
            next = iter.get_next(datetime)
            logger.debug(f"Executing {module} next at {next.strftime('%Y-%m-%d %H:%M:%S')}")

            while True:
                if datetime.now() > next:
                    client2 = mqttwrapper(client, name)
                    if getattr(module, 'run', None):
                        try:
                            module.run(client2)
                            client2.publish(Path(args.s).name + '/rc', payload=0)
                        except Exception as ex:
                            client2.publish(Path(args.s).name + '/rc', payload=1)
                            client2.publish(Path(args.s).name + '/last_error', payload=str(ex))
                            logger.error(ex)
                            time.sleep(1)
                    break
                time.sleep(0.5)

            while next < datetime.now():
                next = iter.get_next(datetime)

        except Exception as ex:
            logger.error(ex)
            time.sleep(1)

def start_broker():
    logger.info(f"Starting script at {args.s}")

    client = mqtt.Client(client_id=f"autobot-{name}-{args.s})", protocol=mqtt.MQTTv5)
    client.on_connect = on_connect
    client.on_message = on_message

    logger.info(f"Connecting to {config['broker']}")
    client.connect(config['broker']['ip'], config['broker'].get('port', 1883), 60)

    module = list(iterate_modules())[0]

    if getattr(module, 'SCHEDULERS', None):
        for scheduler in module.SCHEDULERS:
            t = threading.Thread(target=run_iter, args=(client, scheduler, module))
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
    processes.pop(processes.index(proc))

def kill_all_processes():
    timeout_sec = 1
    for p in processes:
        kill_proc(p, timeout_sec)

def cleanup():
    kill_all_processes()


if __name__ == '__main__':
    atexit.register(cleanup)

    if not args.s:
        start_main()
    else:
        script = Path(args.s)
        start_broker()
