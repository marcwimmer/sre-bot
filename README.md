Remote bot on machines to auto collect data.

Virtualenv
============================


Capabilities in bots:
============================


HOSTNAME = "my-virtual-host1"


SCHEDULERS = ["*/10 * * * * *"]

def run(client):
    client.publish('house/bulb5', payload='off', qos=2)

def onmessage(client, msg, payload=None):
    ...
