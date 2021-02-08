SCHEDULERS = ["* * * * * */1"]
import time

def how_often():
    return True

def run(client):
    client.publish('house/bulb1', payload='on')
    client.publish('house/bulb2', payload='on')
    client.publish('house/bulb3', payload='off')
    time.sleep(1)
