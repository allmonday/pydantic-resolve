# define ER manager class

# define html template for display

import json
import http.server
import socketserver
import threading

PORT = 8001

# 定义 HTML 内容
html_template = """

<!DOCTYPE html>
<html lang="en">
  <head>
    <title>Vis Network | Basic usage</title>

    <script
      type="text/javascript"
      src="https://visjs.github.io/vis-network/standalone/umd/vis-network.min.js"
    ></script>

    <script
      type="text/javascript"
      src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js"
    ></script>

    <style type="text/css">
      #mynetwork {
        width: 600px;
        height: 400px;
        border: 1px solid lightgray;
      }
    </style>
  </head>
  <body>
    <p>Create a simple network with some nodes and edges.</p>

    <div id="mynetwork"></div>

    <script type="text/javascript">
        $().ready(() => {
            fetch('./api/data').then(res => res.json()).then(res => {
                var nodes = new vis.DataSet(res.nodes);
                var edges = new vis.DataSet(res.edges);

                // create a network
                var container = document.getElementById("mynetwork");
                var data = {
                    nodes: nodes,
                    edges: edges,
                };
                var options = {};
                var network = new vis.Network(container, data, options);
            })
        })
    </script>
  </body>
</html>
"""

def get_data():
    nodes = [
        { 'id': 1, 'label': "Node 1" },
        { 'id': 2, 'label': "Node 2" },
        { 'id': 3, 'label': "Node 3" },
        { 'id': 4, 'label': "Node 4" },
        { 'id': 5, 'label': "Node 5" },
    ]

    edges = [
        { 'from': 1, 'to': 3 },
        { 'from': 1, 'to': 2 },
        { 'from': 2, 'to': 4 },
        { 'from': 2, 'to': 5 },
        { 'from': 3, 'to': 3 },
    ]

    data = {
        'nodes': nodes,
        'edges': edges,
    }
    return data


data = get_data()

# 创建一个请求处理器类
class MyRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == '/':
                # 设置响应状态码和头部
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(html_template.encode('utf-8'))

            elif self.path == '/api/data':
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode('utf-8'))

            else:
                self.send_error(404, "File Not Found")
        except BrokenPipeError:
            self.send_error(500, 'borken pipeline')

# 设置处理器
Handler = MyRequestHandler

class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

# 创建服务器
httpd = ReusableTCPServer(("", PORT), Handler)


shutdown_event = threading.Event()

def control_thread_t():
    input("Press Enter to shutdown the server...\n")
    shutdown_event.set()
    print('set')
    httpd.shutdown()
    httpd.server_close()
    print('released')

print(f"Serving at port {PORT}")

server_thread = threading.Thread(target=httpd.serve_forever)
server_thread.start()

control_thread = threading.Thread(target=control_thread_t)
control_thread.start()

server_thread.join()

print('end')