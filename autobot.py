#!/usr/bin/env python3
import simplejson
import traceback
import arrow
import stat
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
from datetime import datetime, timedelta
import threading
import inquirer
import socket
import http.server
from contextlib import contextmanager

VERSION = '0.1'

config_file = Path("/etc/sre/autobot.conf")
if config_file.exists():
    try:
        config = json.loads(config_file.read_text())
    except Exception:
        print("config file corrupt:")
        print(config_file.read_text())
        sys.exit(0)
else: config = {}


FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('')  # root handler
current_dir = Path(sys.path[0])

PROC = namedtuple("Process", field_names=("process", "path", "md5"))

parser = argparse.ArgumentParser(description='Bot SRE', epilog="""

Easily runs observing scripts and publishes to mqtt. Receiving also possible.

""")
parser.add_argument('-s', metavar="Script", type=str, required=False)
parser.add_argument('-l', '--logs', action="store_true")
parser.add_argument('-d', '--daemon', action="store_true")
parser.add_argument('-i', '--install', required=False, action='store_true')
parser.add_argument('-n', '--new', required=False)
parser.add_argument('-ir', '--install-requirements', required=False)
parser.add_argument('-t', '--testbot', required=False)
parser.add_argument('-1', '--exec-once-now', required=False, help="Ignores schedules and executes run of bot now")
parser.add_argument('--list-bots', action="store_true")
parser.add_argument('--pull-bots', action="store_true")

args = parser.parse_args()


logging.getLogger().setLevel(config.get("log_level", "INFO").upper())
default_bots_path = Path('/etc/sre/bots.d')

processes = []

def make_new_file():

    new_name = args.new
    for c in " ":
        new_name = new_name.replace(c, "_")
    dest_path = default_bots_path / (new_name + ".py")
    if dest_path.exists():
        print(f"Already exists: {dest_path}")
        sys.exit(-1)
    template = (current_dir / 'install' / 'bot.template.py').read_text()
    dest_path.write_text(template)

def make_install():
    global config
    name = 'autobot.service'

    bin_autobot = Path('/usr/local/bin/autobot')
    bin_autobot.write_text("""#!/bin/bash
{}/autobot.py "$@"
""".format(current_dir))
    os.chmod(bin_autobot, os.stat(bin_autobot).st_mode | stat.S_IEXEC)
    print(f"autobot is now in path, you can call him from anywhere.")

    if not config_file.exists():
        config = json.loads((current_dir / 'install' / 'autobot.conf').read_text())
        config.setdefault('bots-paths', [])
        config.setdefault('name', socket.gethostname())
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(config, indent=4))

    for script_path in iterate_scripts():
        req_file = script_path.parent / 'requirements.txt'
        if req_file.exists():
            subprocess.check_call(["pip3", "install", '-r', req_file])
        mod = load_module(script_path)
        if getattr(mod, 'install', None):
            mod.install(config_file.parent)

    subprocess.call(["/bin/systemctl", "stop", name])
    template = (current_dir / 'install' / name).read_text()
    template = template.replace('__path__', str(current_dir / 'autobot.py'))
    (Path("/etc/systemd/system/") / name).write_text(template)
    subprocess.check_call(["/bin/systemctl", "daemon-reload"])
    subprocess.check_call(["/bin/systemctl", "enable", name])
    subprocess.check_call(["/bin/systemctl", "restart", name])
    print("")
    print("Start the autobot with:")
    print(f'systemctl start {name}')
    print("")
    print(f"Add custom bots in {default_bots_path} using autobot.py --new ....")
    print(f"Clone existing bots to {default_bots_path}")
    print(f"I setup following name: {config['name']}.")
    print(f"{config_file}:")
    print(config_file.read_text())
    sys.exit(0)

def _get_md5(filepath):
    if not filepath.exists():
        return ''
    m = hashlib.md5()
    m.update(filepath.read_bytes())
    return m.hexdigest()

def start_proc(path):
    logger.info(f"Starting {path}...")
    path = path.absolute()

    os.system(f"pkill -9 -f '{path}'")

    process = subprocess.Popen([
        sys.executable,
        current_dir / 'autobot.py',
        '-s', path,
    ])
    md5 = _get_md5(path)
    processes.append(PROC(process=process, path=path, md5=md5))

def _get_bots_paths():
    bots_paths = [
        default_bots_path,
    ]

    for path in [
        default_bots_path,
    ] + config.get('bots-paths', []):
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

def iterate_scripts():
    result = set()

    def _collect():
        for bots_path in _get_bots_paths():
            for script in bots_path.glob("*.py"):
                if script.name.startswith("__"):
                    continue
                yield script
    for x in _collect():
        result.add(x)
    return sorted(list(result))


@contextmanager
def _onetime_client(timeout=10):
    data = {'stop': False}
    def on_publish(client, userdata, mid):
        data['stop'] = True

    client = _get_regular_client(name_appendix="_webtrigger")
    client.on_publish = on_publish
    _connect_client(client)
    yield client
    timeout = arrow.get().shift(seconds=timeout)
    while not data['stop'] and arrow.get() < timeout:
        client.loop(0.1)
    client.disconnect()

class Handler(http.server.SimpleHTTPRequestHandler) :
    # A new Handler is created for every incommming request tho do_XYZ
    # methods correspond to different HTTP methods.

    def do_POST(self):
        if self.path != "/":
            self.data_string = self.rfile.read(int(self.headers['Content-Length']))
            data = simplejson.loads(self.data_string)

            if self.path.startswith("/trigger/"):
                with _onetime_client() as client:
                    data = json.dumps(data).encode('utf-8')
                    client.publish(self.path[1:], data, 2)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

def start_webserver():
    if not config.get("http_server"):
        return

    http_server = http.server.HTTPServer(
        (config['http_address'], int(config['http_port'])
    ), Handler)
    http_server.serve_forever()

def start_main():
    t = threading.Thread(target=start_webserver,)
    t.daemon = True
    t.start()

    while True:
        for proc in processes:
            if _get_md5(proc.path) != proc.md5:
                logger.info(f"Script was changed, restarting: {proc.path}")
                kill_proc(proc, 1)
                start_proc(proc.path)

        for script in iterate_scripts():
            if not [x for x in processes if x.path == script]:
                logger.info(f"Detected new script: {script}")
                start_proc(script)

        for proc in processes:
            if not [x for x in list(iterate_scripts()) if x == proc.path]:
                logger.info(f"Detected removal of script: {script}")
                kill_proc(proc, 1)

        time.sleep(1)

class mqttwrapper(object):
    def __init__(self, client, hostname, modulename):
        self.client = client
        self.hostname = hostname
        self.logger = logger
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
    logger.info(f"on_message:{args.s}: {msg.topic} {str(msg.payload)}")
    for module in iterate_modules():
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
                logger.error(traceback.format_exc())
                logger.error(ex)

    if msg.topic.startswith("_autobot/console"):
        try:
            answer_autobot_console(client, msg, userdata)
        except Exception as ex:
            breakpoint()
            logger.error(ex)


def answer_autobot_console(client, msg, userdata):
    splitted = msg.topic.split("/")[2:]  # remove _autobot/console
    console_id = splitted[0]

    if splitted[1] == 'ask_for_capabilities':
        response_console_capabilities(client, console_id)
    elif splitted[1] == 'where are you':
        response_console_where_are_you(client, console_id)
    elif splitted[1] == 'update':
        response_console_update(client, console_id)

def response_console_capabilities(client, console_id):
    caps = []
    caps.append('where are you')
    caps.append('update')
    client.publish(
        f"_autobot/console/{console_id}/capabilities/{name}",
        payload=','.join(caps),
        qos=2,
    )


def response_console_update(client, console_id):
    try:
        subprocess.check_call(["/usr/bin/git"], cwd=current_dir)
        subprocess.check_call(["/usr/bin/systemctl", "restart", "autobot"], cwd=current_dir)
    except Exception:
        success = False
    else:
        success = True

    client.publish(
        f"_autobot/console/{console_id}/answer",
        payload=f"Update autobot on {socket.gethostname()} version: {VERSION}: {'success' if success else 'failed'}",
        qos=2,
    )

def response_console_where_are_you(client, console_id):
    answer = []
    answer.append(f"Host: {socket.gethostname()}: {args.s} [version: {VERSION}]")

    client.publish(
        f"_autobot/console/{console_id}/answer",
        payload=','.join(map(str, answer)),
        qos=2,
    )

def run_iter(client, scheduler, module):
    base = datetime.now()
    iter = croniter.croniter(scheduler, base)
    while True:
        try:
            next = iter.get_next(datetime)
            logger.debug(f"Executing {module} next at {next.strftime('%Y-%m-%d %H:%M:%S')}")

            while True:
                if datetime.now() > next:

                    client2 = _get_mqtt_wrapper(client, module)
                    if getattr(module, 'run', None):
                        try:
                            logger.debug(f"Running {args.s}:run")
                            module.run(client2)
                            client2.publish(Path(args.s).name + '/rc', payload=0)
                        except Exception as ex:
                            client2.publish(Path(args.s).name + '/rc', payload=1)
                            client2.publish(Path(args.s).name + '/last_error', payload=str(ex))
                            client2.publish('/last_error', payload=f"{args.s}\n{ex}")
                            logger.error(ex)
                            time.sleep(1)
                    break
                time.sleep(0.5)

        except Exception as ex:
            logger.error(ex)
            time.sleep(1)

def _get_regular_client(name_appendix=None):
    local_name = name
    if name_appendix:
        local_name += name_appendix
    client = mqtt.Client(client_id=f"autobot-{local_name}-{args.s})", protocol=mqtt.MQTTv5)
    return client

def _connect_client(client):
    client.connect(config['broker']['ip'], config['broker'].get('port', 1883), 60)

def start_broker():
    logger.info(f"Starting script at {args.s}")

    client = _get_regular_client()
    client.on_connect = on_connect
    client.on_message = on_message

    logger.info(f"Connecting to {config['broker']}")
    _connect_client(client)

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

class PseudoClient(object):
    def __init__(self):
        pass

    def publish(self, path, payload=None, qos=0):
        print(f"{path}:{qos}: {payload}")

def test_bot(name):
    if not name:
        scripts = list(set(iterate_scripts()))
        for mod in scripts:
            print(mod.name)
            del mod
        return

    filtered = list(filter(lambda x: args.testbot in x.name, iterate_scripts()))
    if len(filtered) != 1:
        print(f"No bot found for {args.testbot}.")
        return
    mod = load_module(filtered[0])
    mod.run(PseudoClient())

def run_once(name):
    filtered = list(filter(lambda x: args.exec_once_now in x.name, iterate_scripts()))
    if len(filtered) != 1:
        print(f"No bot found for {args.exec_once_now}.")
        return
    mod = load_module(filtered[0])
    reg_client = _get_regular_client()
    _connect_client(reg_client)
    client = _get_mqtt_wrapper(reg_client, mod)
    reg_client.loop_start()
    mod.run(client)
    print("Running mqtt for 4 seconds to publish items")
    time.sleep(4)
    reg_client.disconnect()
    reg_client.loop_stop()

def pull_bots():
    for script in iterate_scripts():
        git_dir = script.parent / '.git'
        if git_dir.exists():
            print(f"Executing git pull in {git_dir.parent}")
            subprocess.call(['git', 'pull'])

def show_logs():
    subprocess.run(["journalctl", "-u", "autobot"])


if __name__ == '__main__':
    name = config['name']
    if args.new:
        make_new_file()
        sys.exit(0)

    if args.install:
        make_install()
        sys.exit(0)

    if args.testbot:
        test_bot(args.testbot)
        sys.exit(0)

    if args.exec_once_now:
        run_once(args.exec_once_now)
        sys.exit(0)

    if args.list_bots:
        for script in iterate_scripts():
            print(script)
        sys.exit(0)

    if args.pull_bots:
        pull_bots()
        sys.exit(0)

    if args.logs:
        show_logs()
        sys.exit(0)

    atexit.register(cleanup)

    if not args.s:
        if args.daemon:
            start_main()
        else:
            print("Please call with --daemon.")
    else:
        script = Path(args.s).absolute()
        start_broker()
