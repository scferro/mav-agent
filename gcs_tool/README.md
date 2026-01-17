# MAVLink Agent - GCS Tool

Web-based Ground Control Station for MAVLink Agent.

## Quick Start

### Option 1: Run GCS Locally (Recommended for Development)

```bash
# Start LLM server (from root directory)
cd ..
docker-compose up -d

# Start GCS locally
python gcs_server.py --llm-server=http://localhost:5000

# Open browser
http://localhost:8080
```

### Option 2: Run GCS in Docker

```bash
# Make sure LLM server is running (from root directory)
cd ..
docker-compose up -d

# Start GCS container
cd gcs_tool
docker-compose up -d

# Open browser
http://localhost:8080
```

## Connecting to SITL

```bash
# Terminal 1: Start SITL
sim_vehicle.py -v ArduCopter --console --map

# Terminal 2: Start LLM server (root directory)
cd /path/to/mav-agent
docker-compose up -d

# Terminal 3: Start GCS (this directory)
cd gcs_tool
python gcs_server.py
# OR
docker-compose up

# Browser
http://localhost:8080
```

## Configuration

GCS server connects to:
- **LLM Server:** `http://localhost:5000` (change with `--llm-server`)
- **SITL:** `udp:localhost:14550` (change with `--mavlink`)

## Requirements

- Python 3.10+
- Access to LLM server (running on host or in Docker)
- Optional: SITL for drone simulation
