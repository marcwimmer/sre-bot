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


    test = zapi.host.get(host_id)
    interfaces = zapi.do_request('hostinterface.get', {
        'hostids': host_id,
    })
    interfaceid = interfaces['result'][0]['interfaceid']


print(hostname)
