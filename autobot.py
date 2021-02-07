#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import argparse
import sys
from pathlib import Path
from importlib import import_module
import os
import croniter


parser = argparse.ArgumentParser(description='Bot SRE')
parser.add_argument('-H', metavar="Host", type=str, help='mosquitto host', required=True, default='mqtt.eclipse.org')
parser.add_argument('-p', metavar="Port", type=int, default=1833)
parser.add_argument('-n', metavar="Name", type=str, required=True)
args = parser.parse_args()

# simple eval of
name = args.n
server = args.H
port = args.p

bots_path = Path(os.getcwd())
import pudb
pudb.set_trace()

class mqttwrapper(object):
    def __init__(self, client, hostname):
        self.client = client
        self.hostname = hostname

    def publish(self, path, payload=None, qos=0, retain=False):
        path = self.hostname + '/' + path
        self.client.publish(
            path,
            payload=payload,
            qos=qos,
            retain=retain
        )

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    pass
    #print("Connected with result code " + str(rc))

    client.subscribe("$SYS/#")

    client.publish('test', payload=None, qos=0, retain=False)


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    pass
    print(msg.topic + " " + str(msg.payload))

    for file in bots_path.glob("bots.d/*"):
        p, m = name.rsplit('.', 1)
        mod = import_module(p)
        met = getattr(mod, m)


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(server, port, 60)

import pudb
pudb.set_trace()
while True:
    client2 = mqttwrapper(client, args.n)
    for file in bots_path.glob("bots.d/*"):
        p, m = name.rsplit('.', 1)
        mod = import_module(p)
        met = getattr(mod, m)
    client.loop()
