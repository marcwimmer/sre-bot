# SCHEDULERS = ["* * * * * */1"]

def run(client):
    client.publish('house/bulb1', payload='on')

def on_message(client, userdata, msg):
    print(msg.topic)
