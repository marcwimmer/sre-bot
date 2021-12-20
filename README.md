Remote bot on machines to auto collect data.

Setup
=============

  * config file /etc/sre/autobot.conf
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
    # used for webhook trigger
    "http_address": "0.0.0.0",
    "http_port": 8520,
}
```
  * checkout bot repo
  * ./autobot.py -i 

Bot
============================

  * place file in one of the searched directories

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


Calling a webhook
================================

  * call http://address:port/trigger/mymachine/restart and a msg with topci "mymachine/restart" is send
  * useful together with zabbix


