# https://pypi.org/project/py-zabbix/
# https://www.zabbix.com/documentation/current/manual/api/reference/hostinterface/get
url = "http://10.10.173.111:8888"
user = "Admin"
password = "zabbix"
import uuid

from pyzabbix.api import ZabbixAPI
hostname = str(uuid.uuid4())

with ZabbixAPI(url=url, user=user, password=password) as zapi:
    hosts = zapi.do_request('host.get', {
        "filter": {
            "host": [
                "Zabbix server",
                "Linux server"
            ]
        }
    })
    print(hosts)
    print("-----------------")
    res = zapi.do_request('host.get', {
        "output": ["hostid"],
        "selectGroups": "extend",
        "filter": {
            "host": [
                "Zabbix server"
            ]
        }
    })
    print(res)
    print("-----------------")

    res = zapi.do_request('host.create', {
        'host': hostname,
        # requires a host interface for items later
        "interfaces": [
            {
                "type": 1,
                "main": 1,
                "useip": 1,
                "ip": "127.0.0.1",
                "dns": "",
                "port": "10050"
            }
        ],
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
    })
    host_id = res['result']['hostids'][0]

    test = zapi.host.get(host_id)
    interfaces = zapi.do_request('hostinterface.get', {
        'hostids': host_id,
    })
    interfaceid = interfaces['result'][0]['interfaceid']

    res = zapi.do_request('item.create', {
        "name": "Free disk space on /home/joe/",
        "key_": "mykey1",
        "hostid": host_id,
        "type": 0,
        "value_type": 3,
        "interfaceid": interfaceid,
        "delay": "1s"
    })
    item_id = res['result']['itemids'][0]

print(hostname)
