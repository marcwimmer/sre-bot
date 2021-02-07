from pyzabbix import ZabbixMetric, ZabbixSender


def on_message(msg):
    import pudb
    pudb.set_trace()
    packet = [
        ZabbixMetric(hostname, key, 2),
    ]
    result = ZabbixSender(use_config=True).send(packet)
