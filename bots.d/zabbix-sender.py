from pyzabbix import ZabbixMetric, ZabbixSender


def on_message(client, userdata, msg):
    hostname = msg.topic.split("/")[0]
    key = '.'.join(msg.topic.split("/")[1:])
    value = msg.payload or ''
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    packet = [
        ZabbixMetric(hostname, key, value),
    ]
    print(f"zb send now {packet}")
    result = ZabbixSender(use_config=True).send(packet)
    client.logger.debug(result)
