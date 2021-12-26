Remote bot on machines to auto collect data.

Installation:
============================

Recommended way is to use a virtual-env like:

```bash
python3 -m venv /var/lib/sre-bot
. /var/lib/sre-bot/bin/activate
pip install wheel
pip install sre-bot
```



Capabilities in bots:
============================


```python
HOSTNAME = "my-virtual-host1"


SCHEDULERS = ["*/10 * * * * *"]

def run(client):
    client.publish('house/bulb5', payload='off', qos=2)

def on_message(client, msg, payload=None):
    ...

# optional:
def install():
    pass
```
## How to upload new version
  * increase version in setup.py
  * one time: pipenv install twine --dev
  * pipenv shell
  * python3 setup.py upload

## install directly

pip install git+https://github.com/marcwimmer/gimera