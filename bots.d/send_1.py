def how_often():
    return True

def run(client):
    client.publish('house/bulb1', 'on')
