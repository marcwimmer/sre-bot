from pyzabbix.api import ZabbixAPI
import json
from pathlib import Path
config = json.loads(Path("/etc/sre/zabbix.conf").read_text())

def _get_hosts(zapi, hostname):
    hosts = zapi.do_request('host.get', {
        "filter": {
            "host": [
                hostname,
            ]
        }
    })
    return hosts['result']

def _create_host(zapi, hostname):
    info = {
        'host': hostname,
        # requires a host interface for items later
        # "interfaces": [
        # {
        # "type": 1,
        # "main": 1,
        # "useip": 1,
        # "ip": "127.0.0.1",
        # "dns": "",
        # "port": "10050"
        # }
        # ],
        "groups": [
            {
                "groupid": "4"
            }
        ],
        "tags": [
            {
                "tag": "Host name",
                "value": "Linux server"
            }
        ],
        "inventory_mode": 0,
    }
    res = zapi.do_request('host.create', info)
    host_id = res['result']['hostids'][0]
    return host_id

def _get_item(zapi, hostid, item_key):
    res = zapi.do_request('item.get', {
        "hostids": hostid,
        "output": "extend",
        "search": {
            "key_": item_key,
        },
    })
    return res['result']

def _create_item(zapi, hostid, item_key, name, ttype):
    value_type = {
        'char': 1,
        'float': 0,
        'int': 3,
        'log': 2,
        'text': 4,
    }[ttype]

    res = zapi.do_request('item.create', {
        "name": item_key,
        "key_": item_key,
        "hostid": hostid,
        "type": 2, # Zabbix trapper to enable zabbix-send
        "value_type": value_type,
        "delay": "1s"
    })
    item_id = res['result']['itemids'][0]
    return item_id

def on_message(client, userdata, msg):
    hostname = msg.topic.split("/")[0]
    key = '.'.join(msg.topic.split("/")[1:])

    with ZabbixAPI(url=config['url'], user=config['user'], password=config['password']) as zapi:
        hosts = _get_hosts(zapi, hostname)
        if not hosts:
            host_id = _create_host(zapi, hostname)
        else:
            host_id = hosts[0]['hostid']

        item = _get_item(zapi, host_id, key)
        if not item:
            if isinstance(msg.payload, (int,)):
                ttype = 'int'
            else:
                ttype = 'char'
            _create_item(zapi, host_id, key, key, ttype)
