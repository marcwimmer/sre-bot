Remote bot on machines to auto collect data.

Virtualenv
============================


Capabilities in bots:
============================

HOSTNAME = "my-virtual-host1"
SCHEDULERS = ["*/10 * * * * *"]

def run(client):
    client.publish('house/bulb5', payload='off', qos=2)

def on_message(client, msg, payload=None):
    ...

Minimum configuration in /etc/sre/autobot.conf
-----------------------------------------------
{
    "bots-paths": [
        "/home/sre/autobots/bots",
        "/home/sre/autobots/test-bots"],
    "broker": {
        "ip": "ip_of_broker"
    },
    "name": "myhost1",
    "http_address": "0.0.0.0",
    "http_port": 8520,
    "log_level": "debug"
}