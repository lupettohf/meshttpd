import cherrypy
import threading
import time
from pubsub import pub
import meshtastic
import meshtastic.tcp_interface
import json
import datetime
import hashlib
import random

class MeshAPI(object):
    def __init__(self, hostname='meshtastic.local'):
        """
        Initialize the MeshAPI.

        Args:
            hostname (str): The hostname or IP address of the Meshtastic device.
        """
        self.hostname = hostname
        self.iface = None
        self.whoami = None
        self.device_telemetry_cache = {}  # Cache to store device telemetry data
        self.environment_telemetry_cache = {}  # Cache to store environment telemetry data
        self.message_cache = {}  # Cache to store messages
        self.seen_nodes = {}  # Dictionary to store information about seen nodes
        self.connection_attempts = 0  # Number of connection attempts made
        self.last_connection_time = None  # Time of the last successful connection
        self.connection_thread = threading.Thread(target=self.connect_to_mesh, daemon=True)

    def on_receive(self, packet, interface):  
        """
        Callback function called when a packet arrives.
        """
        # Debug
        print(f"Received: from={packet.get('from')} to={packet.get('to')} portnum={packet['decoded'].get('portnum', 'UNKNOWN')}")

        # Check if the received packet contains telemetry data
        if 'decoded' in packet and 'telemetry' in packet['decoded']:
            node_id = packet['from']
            telemetry_data = packet['decoded']['telemetry']
            
            # Check if telemetry data contains deviceMetrics
            if 'deviceMetrics' in telemetry_data:
                self.device_telemetry_cache[node_id] = {
                    "time": telemetry_data["time"],
                    "deviceMetrics": {
                        "batteryLevel": telemetry_data["deviceMetrics"].get("batteryLevel"),
                        "voltage": telemetry_data["deviceMetrics"].get("voltage"),
                        "channelUtilization": telemetry_data["deviceMetrics"].get("channelUtilization"),
                        "airUtilTx": telemetry_data["deviceMetrics"].get("airUtilTx")
                    }
                }
                
            # Check if telemetry data contains environmentMetrics
            if 'environmentMetrics' in telemetry_data:
                self.environment_telemetry_cache[node_id] = {
                    "time": telemetry_data["time"],
                    "environmentMetrics": {
                        "temperature": telemetry_data["environmentMetrics"].get("temperature"),
                        "relativeHumidity": telemetry_data["environmentMetrics"].get("relativeHumidity"),
                        "barometricPressure": telemetry_data["environmentMetrics"].get("barometricPressure")
                    }
                }

        # Check if the received packet is a message
        if 'decoded' in packet and 'text' in packet['decoded']:
            node_id = packet['from']
            message_data = packet['decoded']['text']
            internal_message_id = self.generate_internal_message_id(node_id, message_data)
            self.message_cache[internal_message_id] = {"node_id": node_id, "message": message_data}
            if len(self.message_cache) > 100:
                self.message_cache.pop(0)
                
        # Update seen nodes dictionary
        if 'fromId' in packet:
            node_id = packet['from']
            long_id = packet['fromId']
            if node_id not in self.seen_nodes:
                self.seen_nodes[node_id] = {"long_id": long_id}

    def on_connection(self, interface, topic=pub.AUTO_TOPIC):  
        """
        Callback function called when we (re)connect to the radio.
        """
        self.last_connection_time = time.time()
        self.connection_attempts += 1
        self.whoami = self.iface.myInfo.my_node_num
        print(f"Connected to Meshtastic device at {self.hostname}")

    @cherrypy.expose
    def index(self):
        """
        Exposed endpoint for the index page.
        """
        html = """
        <html>
        <head><title>Meshttpd Poor Man's Swagger</title></head>
        <style>
        body {
            font-family: Arial, sans-serif;
            background-image: url('data:image/png;base64,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');
            background-repeat: no-repeat;
            background-position: right;
            background-position-y: center;
            background-position-y: 1px;
        }
        h1 {
            color: #333;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 10px;
        }
        li a {
            color: #007bff;
            text-decoration: none;
        }
        </style>
        <body>
        <h1>Meshttpd Poor Man's Swagger</h1>
        <h2>Endpoints:</h2>
        <ul>
            <li>
                <a href="/api/mesh/send_message">/api/mesh/send_message</a>: POST endpoint to send a message
                <ul>
                    <li>Parameters:
                        <ul>
                            <li><b>message</b> (str): The message to be sent.</li>
                            <li><b>node_id</b> (optional, str): The ID of the node to which the message should be sent.</li>
                        </ul>
                    </li>
                </ul>
            </li>
            <li>
                <a href="/api/mesh/get_device_telemetry">/api/mesh/get_device_telemetry</a>: GET endpoint to retrieve device telemetry data
            </li>
            <li>
                <a href="/api/mesh/get_environment_telemetry">/api/mesh/get_environment_telemetry</a>: GET endpoint to retrieve environment telemetry data
            </li>
            <li>
                <a href="/api/mesh/get_last_messages">/api/mesh/get_last_messages</a>: GET endpoint to retrieve the last cached messages
            </li>
            <li>
                <a href="/api/mesh/delete_message">/api/mesh/delete_message</a>: POST endpoint to delete a message from the cache
                <ul>
                    <li>Parameters:
                        <ul>
                            <li><b>message_id</b> (str): The ID of the message to be deleted.</li>
                        </ul>
                    </li>
                </ul>
            </li>
            <li>
                <a href="/api/mesh/nodes">/api/mesh/nodes</a>: GET endpoint to list all seen nodes
            </li>
            <li>
                <a href="/api/mesh/status">/api/mesh/status</a>: GET endpoint to check connection status
            </li>
        </ul>
		<p>Made by luhf for <a href="https://monocul.us">Monocul.us Mesh</a></p>
        </body>
        </html>
        """
        return html

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def send_message(self, message=None, node_id=None):
        """
        Exposed endpoint for sending a message.

        Args:
            message (str): The message to be sent.
            node_id (optional, str): The ID of the node to which the message should be sent.

        Returns:
            dict: A JSON object containing the status of the operation.

        Raises:
            404 (Missing parameters): If the `message` parameter is missing.
            400 (Invalid node ID): If the specified node ID is invalid.
        """
        if message is None:
            cherrypy.response.status = 404
            return {"error": "Missing parameters: message"}
        try:
            if self.iface:
                if node_id:
                    try:
                        self.iface.sendText(message, node_id)
                    except meshtastic.node_manager.NodeIdNotFound:
                        raise cherrypy.HTTPError(400, "Invalid node ID")
                else:
                    self.iface.sendText(message)
                return {"status": "success", "message": "Message sent successfully"}
            else:
                return {"status": "error", "message": "Mesh interface not initialized"}
        except Exception as ex:
            return {"status": "error", "message": str(ex)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_device_telemetry(self):
        """
        Exposed endpoint for retrieving device telemetry data from connected nodes.
        """
        return self.device_telemetry_cache

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_environment_telemetry(self):
        """
        Exposed endpoint for retrieving environment telemetry data from connected nodes.
        """
        return self.environment_telemetry_cache

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_last_messages(self):
        """
        Exposed endpoint for retrieving the last X cached messages.
        """
        return self.message_cache

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def delete_message(self, message_id=None):
        """
        Exposed endpoint for deleting a message from the cache.

        Args:
            message_id (str): The ID of the message to be deleted.

        Returns:
            dict: A JSON object containing the status of the operation.

        Raises:
            404 (Missing parameters): If the `message_id` parameter is missing.
            400 (Invalid message ID): If the specified message ID is invalid.
        """
        if message_id is None:
            cherrypy.response.status = 404
            return {"error": "Missing parameters: message_id"}
        if message_id not in self.message_cache:
            raise cherrypy.HTTPError(400, "Invalid message ID")
        del self.message_cache[message_id]
        return {"status": "success", "message": "Message deleted successfully"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def nodes(self):
        """
        Exposed endpoint for listing all seen nodes.
        """
        return self.seen_nodes

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self):
        """
        Exposed endpoint for checking connection status.
        """
        return {
            "connected": bool(self.iface),
            "nodeid": str(self.whoami),
            "last_connection_time": self.last_connection_time,
            "total_connection_attempts": self.connection_attempts
        }

    def connect_to_mesh(self):
        """
        Function to connect to the Meshtastic device.
        """
        while True:
            try:
                self.iface = meshtastic.tcp_interface.TCPInterface(hostname=self.hostname)
                return
            except Exception as ex:
                print(f"Error: Could not connect to {self.hostname} {ex}")
                time.sleep(1)  # Wait for 1 second before attempting to reconnect

    def generate_internal_message_id(self, node_id, message):
        """
        Function to generate an internal message ID using MD5 hashing of random data, node ID, and message.

        Args:
            node_id (str): The ID of the node.
            message (str): The message.

        Returns:
            str: The generated internal message ID.
        """
        random_data = str(random.random()).encode()
        hash_input = random_data + str(node_id).encode() + message.encode()
        hash_object = hashlib.md5(hash_input)
        return hash_object.hexdigest()[:10]

    def start(self):
        """
        Function to start the connection thread.
        """
        self.connection_thread.start()

if __name__ == '__main__':
    # Change the IP address of the meshtastic device here. 
    # With some networks the local domain will not work, if that is your case use the IP address of the device.
    mesh_api = MeshAPI(hostname='meshtastic.local')

    # Start the connection thread
    mesh_api.start()

    # Subscribe to receive events
    pub.subscribe(mesh_api.on_receive, "meshtastic.receive")
    pub.subscribe(mesh_api.on_connection, "meshtastic.connection.established")


    cherrypy.tree.mount(mesh_api, '/api/mesh')
    #Please use a reverse proxy if you are planning to expose this to the internet!
    #Set server.socket_host to 127.0.0.1 
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    cherrypy.engine.start()
    cherrypy.engine.block()
