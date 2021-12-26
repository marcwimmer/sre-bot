import simplejson
import http.server
import json

class Handler(http.server.SimpleHTTPRequestHandler) :
    # A new Handler is created for every incommming request tho do_XYZ
    # methods correspond to different HTTP methods.

    def do_POST(self):
        from .tools import _onetime_client
        if self.path != "/":
            self.data_string = self.rfile.read(int(self.headers['Content-Length']))
            data = simplejson.loads(self.data_string)

            if self.path.startswith("/trigger/"):
                with _onetime_client("_webtrigger") as client:
                    data = json.dumps(data).encode('utf-8')
                    client.publish(self.path[1:], data, 2)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

def start_webserver():
    from . import global_data
    config = global_data['config'].config
    if not config.get("http_address"):
        return

    http_server = http.server.HTTPServer(
        (config['http_address'], int(config.get('http_port', 8822))
    ), Handler)
    http_server.serve_forever()
