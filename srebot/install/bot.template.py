# SCHEDULERS = ["* * * * * */1"]
# HOSTNAME = 'host1'

def run(client):
    # client.publish('house/bulb1', 'on')
    pass

def on_message(client, msg, payload=None):
    print(msg.topic)


def install():
    pass