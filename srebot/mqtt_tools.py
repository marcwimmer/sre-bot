from . import global_data
from pathlib import Path
import arrow
import json
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
        self.client.publish(
            path,
            payload=json.dumps(value),
            qos=qos,
            retain=retain
        )

def _get_mqtt_wrapper(client, module):
    from . import global_data
    name = global_data['config'].hostname
    _name = getattr(module, "HOSTNAME", name) if module else name
    _modulename = Path(module.__file__).stem
    return mqttwrapper(client, _name, _modulename)

def _get_regular_client(name, scriptfile):
    client = mqtt.Client(client_id=f"autobot-{name}-{scriptfile.name})", protocol=mqtt.MQTTv5)
    return client

def _connect_client(client):
    config = global_data['config']
    client.connect(config.config['broker']['ip'], config.config['broker'].get('port', 1883), 60)

def on_connect(client, userdata, flags, reason, properties):
    global_data['config'].logger.debug(f"Client connected")
    client.subscribe("#")