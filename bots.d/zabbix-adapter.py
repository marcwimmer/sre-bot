url = "http://10.10.173.111:8888"
user = "Admin"
password = "zabbix"

from pyzabbix.api import ZabbixAPI

def on_message(msg):

    import pudb
    pudb.set_trace()

    with ZabbixAPI(url=url, user=user, password=password) as zapi:
        pass
