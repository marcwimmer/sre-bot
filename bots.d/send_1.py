import time
SCHEDULERS = ["* * * * * */10"]

def run(client):
    client.publish('house/bulb1', payload='on5', qos=2)
    # client.publish('house/bulb2', payload='on', qos=2)
    # client.publish('house/bulb3', payload='off', qos=2)
    print("publish now")
