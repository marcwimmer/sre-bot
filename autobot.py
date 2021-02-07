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
from collections import namedtuple
config = json.loads(Path("/etc/sre/autobot.conf").read_text())


FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('')  # root handler


parser = argparse.ArgumentParser(description='Bot SRE')
parser.add_argument('-s', metavar="Script", type=str, required=False)
parser.add_argument('-l', metavar="Level", type=str, required=False, default='INFO')
args = parser.parse_args()

name = config['name']

logging.getLogger().setLevel(args.l.upper())

bots_path = Path(os.getcwd()) / 'bots.d'
sys.path.append(bots_path)

processes = []

def start_main():
    for script in bots_path.glob("*.py"):
        if script.name.startswith("__"):
            continue
        process = subprocess.Popen([
            '/usr/bin/python3',
            'autobot.py',
            '-s', script,
            '-l', args.l,
        ])
        processes.append(process)

    while True:
        time.sleep(10)


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


def start_broker():
    logger.info(f"Starting script at {args.s}")

    client = mqtt.Client(protocol=mqtt.MQTTv5)
    client.on_connect = on_connect
    client.on_message = on_message

    logger.info(f"Connecting to {config['broker']}")
    client.connect(config['broker']['ip'], config['broker'].get('port', 1883), 60)

    while True:
        client2 = mqttwrapper(client, name)
        for module in iterate_modules():
            if getattr(module, 'run', None):
                try:
                    module.run(client2)
                except Exception as ex:
                    logger.error(ex)
                    time.sleep(1)
        client.loop_start()
        time.sleep(0.1)


def cleanup():
    timeout_sec = 2
    for p in processes: # list of your processes
        p_sec = 0
        for second in range(timeout_sec):
            if p.poll() is None:
                time.sleep(0.1)
                p_sec += 1
        if p_sec >= timeout_sec:
            p.kill() # supported from python 2.6


if __name__ == '__main__':
    atexit.register(cleanup)

    if not args.s:
        start_main()
    else:
        script = Path(args.s)
        start_broker()
