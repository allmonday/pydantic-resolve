# define ER manager class

# define html template for display

import json
import http.server
import socketserver
import threading
from pydantic import BaseModel
from pydantic_resolve.utils.class_util import get_keys

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
        width: 100%;
        height: 800px;
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
                var options = {
                    layout: {
                        randomSeed: '0.370981731081512:1733477712137'
                    }
                };
                var network = new vis.Network(container, data, options);
                console.log(network.getSeed())
            })
        })
    </script>
  </body>
</html>
"""

class Project(BaseModel):
    id: int
    name: str

class Team(BaseModel):
    id: int
    name: str


class Event(BaseModel):
    id: int
    name: str

class Milestone(BaseModel):
    id: int
    name: str

class ProjectChangeLog(BaseModel):
    id: int
    content: str

class MeetingNote(BaseModel):
    id: int
    title: str
    content: str

class MeetingNoteAttendee(BaseModel):
    id: int
    name: str

class MeetingNoteFollowup(BaseModel):
    id: int
    name: str

class Service(BaseModel):
    id: int
    name: str

class ServiceAdopt(BaseModel):
    id: int
    name: str

def get_data():
    counter = 1
    definitions = [
        dict(source=Project, target=Event, field='owns'),
        dict(source=Project, target=Milestone, field='owns'),
        dict(source=Project, target=ProjectChangeLog, field='generate'),
        dict(source=Project, target=MeetingNote, field='owns'),
        dict(source=MeetingNote, target=MeetingNoteAttendee, field='has'),
        dict(source=MeetingNote, target=MeetingNoteFollowup, field='has'),
        dict(source=Team, target=Service, field='manage'),
        dict(source=Project, target=ServiceAdopt, field='has'),
        dict(source=Service, target=ServiceAdopt, field='belong'),
    ]

    node_map = {}
    nodes = []
    edges = []

    def get_desc(kls):
        name = kls.__name__
        keys = get_keys(kls)
        keys = '\n'.join(['- ' + k for k in keys])
        keys = '\n\n' + keys
        return f"<b>{name}</b>{keys}"

    for d in definitions:
        source = d['source']
        target = d['target']
        source_name = source.__name__
        target_name = target.__name__
        field = d['field']

        font = {
            'font': {'multi': 'html', 'align': 'left'},
            'shape': 'box',
            'color': '#fff', 
        }

        if source_name not in node_map:
            node_map[source_name] = counter
            counter += 1
            nodes.append({ 'id': node_map[source_name], 'label': get_desc(source), **font })

        if target_name not in node_map:
            node_map[target_name] = counter
            counter += 1
            nodes.append({ 'id': node_map[target_name], 'label': get_desc(target), **font })
        
        edges.append({ 
            'from': node_map[source_name],
            'to': node_map[target_name],
            'label': field,
            'physics': { 'springLength': 100 },
            'arrows': { 'to': { 'enabled': True, 'type': 'arrow', 'scaleFactor': 0.4 }} })

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