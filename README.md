Remote bot on machines to auto collect data.

# Setup

Recommended way is to use a virtual-env like:

```bash
python3 -m venv /var/lib/sre-bot
. /var/lib/sre-bot/bin/activate
pip install wheel
pip install sre-bot
```

## First steps:
```bash
sre add-bot-path ./bots
sre new test-bot.py
```

## /etc/sre/sre.conf

```yaml
{
    "bots-paths": [
        "/home/sre/autobots/bots",
        "/home/sre/autobots/test-bots"
    ],
    "broker": {
        "ip": "address of mqtt broker",
        "port": 1883, # optional
    },
    "name": "myhost1",
    "log_level": "error"
    "log_file": "/var/log/sre/.log",
    # used for webhook trigger
    "http_address": "0.0.0.0",
    "http_port": 8520,
}
```
# Bot

  * ```sre new my-bot1``

```python
HOSTNAME = "my-virtual-host1"   # optional otherwise configured default host
SCHEDULERS = ["*/10 * * * * *"] # optional - used when run is given up to seconds

def run(client):
    # requires SCHEDULERS!
    client.publish('house/bulb5', payload='off', qos=2)

def on_message(client, msg, payload=None):
    if '/restart/machine1' in msg.topic:
        ...

```


# Calling a webhook

  * call http://address:port/trigger/mymachine/restart and a msg with topic "mymachine/restart" is sent
  * useful together with zabbix


## Example: Zabbix Trigger

```python
import json

def on_message(client, msg, payload=None):
    if 'trigger/zabbix' in msg.topic:
        data = json.loads(msg.payload.decode('utf-8'))
        if data.get('OPDATA') == 'restart_queuejobs' and data.get("ERROR") == "1":
            client.publish("restart_queuejobs")
```

# Example: Setup Mosquitto for mqtt with docker

```yml
version: '3'
services:
  mosquitto:
      image: eclipse-mosquitto:1.6
      ports:
        - 1883:1883
      restart: unless-stopped
```


# How to upload new version
  * increase version in setup.py
  * one time: pipenv install twine --dev
  * pipenv shell
  * python3 setup.py upload

# install directly

pip3 install git+https://github.com/marcwimmer/sre-bot
