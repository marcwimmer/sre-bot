import traceback
import os
from . import global_data
from pathlib import Path
import arrow
import json
import click
import paho.mqtt.client as mqtt

class PseudoClient(object):
    def __init__(self):
        pass

    def publish(self, path, payload=None, qos=0):
        print(f"{path}:{qos}: {payload}")

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
        self.output_to_console(value)
        self.client.publish(
            path,
            payload=json.dumps(value),
            qos=qos,
            retain=retain
        )

    def output_to_console(self, value):
        if os.getenv("SRE_OUTPUT_MESSAGES") != "1":
            return
        try:
            value = json.dumps(value, indent=4)
        except: pass

        click.secho(str(value), fg='cyan')

def _get_mqtt_wrapper(client, module):
    from . import global_data
    name = global_data['config'].config['name']
    _name = getattr(module, "HOSTNAME", name) if module else name
    _modulename = Path(module.__file__).stem
    return mqttwrapper(client, _name, _modulename)

def _get_regular_client(name, scriptfile):
    client = mqtt.Client(client_id=f"srebot-{name}-{scriptfile.name})", protocol=mqtt.MQTTv5)
    return client

def _connect_client(client):
    config = global_data['config']
    client.connect(config.config['broker']['ip'], config.config['broker'].get('port', 1883), 60)

def on_connect(client, userdata, flags, reason, properties):
    global_data['config'].logger.debug(f"Client connected")
    client.subscribe("#")

def on_message(client, userdata, msg):
    config = global_data['config']
    config.logger.debug(f"on_message: {msg.topic} {str(msg.payload)}")
    from .tools import load_module
    if not config.bot:
        return
    module = load_module(config.bot)
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
            trace = traceback.format_exc()
            config.logger.error(str(ex) + "\n\n" + str(msg) + '\n\n' + trace)

