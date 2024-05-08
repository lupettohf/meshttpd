# meshttpd

meshttpd is a simple REST API that enables interaction with a Meshtastic node via TCP. It provides endpoints to send messages, retrieve device and environment telemetry data, fetch cached messages, list seen nodes, and check connection status.

## Installation

1. Clone the repository:

```bash
git clone https://github.com/lupettohf/meshttpd.git
```
or 
```bash
git clone https://git.monocul.us/andrea/meshttpd.git
```

2. Navigate to the project directory:

```bash
cd meshttpd
```

3. Install dependencies using pip:

```bash
pip install -r requirements.txt
```

## Configuration

To configure the main Python file `meshttpd.py`, you need to specify the IP address or hostname of your Meshtastic device. Modify the `hostname` parameter in the `MeshAPI` class initialization according to your device's network configuration. If your network does not support local domain resolution, use the IP address of the device instead.

```python
# Change the IP address of the meshtastic device here.
mesh_api = MeshAPI(hostname='meshtastic.local')
```

## Usage

Start the server by running `meshttpd.py`:

```bash
python meshttpd.py
```

This will start the server locally. To expose it to the internet, it's recommended to use a reverse proxy.

## Endpoints

- `/api/mesh/send_message`: POST endpoint to send a message.
  - Parameters:
    - `message` (str): The message to be sent.
    - `node_id` (optional, str): The ID of the node to which the message should be sent.

- `/api/mesh/get_device_telemetry`: GET endpoint to retrieve device telemetry data.

- `/api/mesh/get_environment_telemetry`: GET endpoint to retrieve environment telemetry data.

- `/api/mesh/get_last_messages`: GET endpoint to retrieve the last cached messages.

- `/api/mesh/nodes`: GET endpoint to list all seen nodes.

- `/api/mesh/status`: GET endpoint to check connection status.

This project was created by luhf for [Monocul.us Mesh](https://monocul.us).
