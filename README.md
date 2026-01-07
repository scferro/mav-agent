# MAVLink Agent with TensorRT-LLM

Intelligent drone mission planning agent using natural language. Built with LangChain and NVIDIA TensorRT-LLM for GPU-accelerated inference with the Qwen3-4B language model.

## Overview

Transform natural language commands into validated MAVLink drone missions. Say "take off to 150 feet heading north, fly to the park, then survey the area" and the agent handles the rest.

**Key Features:**
- Natural language mission planning
- TensorRT-LLM optimized inference (INT4 AWQ quantization, ~4-5GB VRAM)
- VTOL support with transition heading control
- AI-powered search and detection integration
- Auto-validation and parameter completion
- RESTful API for web interface
- Containerized deployment with Docker

---

## Quick Start

**For existing installations with pre-built containers and engines.**

### 1. Start the Server

```bash
cd <path-to-repo>/px4-agent

# Start server
docker compose up -d

# View logs
docker compose logs -f
```

Server runs on http://localhost:5000

### 2. Test the API

```bash
# Check status
curl http://localhost:5000/api/status

# Send command
curl -X POST http://localhost:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{"user_input": "add takeoff to 150 feet heading north"}'

# Mission planning
curl -X POST http://localhost:5000/api/mission \
  -H "Content-Type: application/json" \
  -d '{"user_input": "create mission with takeoff, waypoint at 41.8840, -87.6330, and RTL"}'
```

### Stop the Server

```bash
docker compose down
```

---

## Building from Scratch

**For first-time setup or rebuilding from clean slate.**

### Prerequisites

**Verify GPU and Docker support:**
```bash
# Check NVIDIA driver
nvidia-smi

# Test Docker GPU access
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

**If GPU test fails:**
```bash
sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

### Step 1: Clone Repository with Submodules

The Qwen3-4B model is included as a git submodule:

```bash
# Clone with submodules
git clone --recursive <your-repo-url>

# Or if already cloned, initialize submodules
cd <path-to-repo>/px4-agent
git submodule update --init --recursive
```

This downloads the Qwen3-4B-Instruct-2507 tokenizer (~8GB) into `models/Qwen3-4B-Instruct-2507/`.

### Step 2: Build AWQ Checkpoint 

```bash
cd <path-to-repo>/px4-agent

# Start TensorRT-LLM container
docker run --rm -it \
  --gpus all \
  --ipc=host \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  -v $(pwd):/workspace \
  -w /workspace \
  nvcr.io/nvidia/tensorrt-llm/release:1.0.0 \
  bash
```

```bash
python3 TensorRT-LLM/examples/models/core/qwen/convert_checkpoint.py \
  --model_dir /workspace/models/Qwen3-4B-Instruct-2507 \
  --output_dir /workspace/models/qwen3_4b_trtllm_checkpoint \
  --dtype float16 \
  --use_weight_only \
  --weight_only_precision int4_awq
```

### Step 3: Build TensorRT Engine

Compile the checkpoint into optimized TensorRT engine (~5-15 minutes):

**Inside container, build engine:**
```bash
trtllm-build \
  --checkpoint_dir /workspace/models/qwen3_4b_trtllm_checkpoint \
  --output_dir /workspace/models/qwen3_4b_trtllm_engine \
  --gemm_plugin float16 \
  --max_batch_size 1 \
  --max_input_len 32768 \
  --max_seq_len 32768
```

**Parameters:**
- `--max_batch_size 1`: Concurrent requests
- `--max_input_len 32768`: Max prompt tokens
- `--max_seq_len 32768`: Max total tokens (input + output)
- `--gemm_plugin float16`: Matrix operation precision

**Test engine:**
```bash
python /workspace/TensorRT-LLM/examples/run.py \
  --engine_dir /workspace/models/qwen3_4b_trtllm_engine \
  --tokenizer_dir /workspace/models/Qwen3-4B-Instruct-2507 \
  --input_text "Explain how to create a drone waypoint mission" \
  --max_output_len 100
```

Exit container when done:
```bash
exit
```

### Step 4: Build MAVLink Agent Docker Image

```bash
cd <path-to-repo>/px4-agent

# Build image
docker compose build mav-agent
```

### Step 5: Configure Paths

Verify `config/default_config.json` uses container paths:

```json
{
  "model_command": {
    "type": "tensorrt",
    "model_path": "/models/qwen3_4b_trtllm_engine/",
    "tokenizer_path": "/models/Qwen3-4B-Instruct-2507/",
    "gpu_memory_fraction": 0.7,
    "temperature": 0.3
  }
}
```

**Path mapping (docker-compose.yml):**
- Host: `./models/Qwen3-4B-Instruct-2507` (git submodule)
- Container: `/models/Qwen3-4B-Instruct-2507/`
- Host: `./models/qwen3_4b_trtllm_engine` (built locally)
- Container: `/models/qwen3_4b_trtllm_engine/`

### Step 6: Run the Server

```bash
docker compose up -d
```

Test with Quick Start instructions above.

---

## Usage

### Mission Item Types

**Takeoff** - Launch with altitude and heading
```
"Take off to 150 feet heading north"
"Takeoff to 200 feet heading southwest"
```

**Waypoint** - Navigate to coordinates
```
"Add waypoint at 41.8840, -87.6330 at 300 feet"
"Fly 2 miles north at 400 feet"
"Go to MGRS 11SMT1234567890"
"Add waypoint searching for vehicles"
```

**Loiter** - Circular orbit pattern
```
"Loiter with 500 foot radius"
"Circle the area at 300 feet with 1000 foot radius"
"Loiter here searching for people"
```

**Survey** - Systematic area coverage
```
"Survey the area with 100 foot spacing"
"Survey 500 foot radius at 200 feet"
```

**RTL** - Return to launch
```
"Return to launch"
"RTL at 200 feet"
```

### Position Specification

**Absolute:**
```
"41.8840, -87.6330"
"Lat 41.8840, Long -87.6330"
```

**Relative:**
```
"2 miles north"
"500 feet southeast"
"1 kilometer northeast of last waypoint"
```

**MGRS Grid:**
```
"MGRS 11SMT1234567890"
```

### Mission Management

**Update items:**
```
"Change item 2 altitude to 400 feet"
"Update loiter radius to 800 feet"
```

**Move items:**
```
"Move item 3 to 41.8850, -87.6340"
"Relocate waypoint 2 half a mile east"
```

**Delete items:**
```
"Delete item 5"
"Remove waypoint 3"
```

**Reorder:**
```
"Move item 5 to position 2"
```

### AI Search Integration

Add search to waypoints, loiter, and survey:
```
"Waypoint at 41.8840, -87.6330 searching for vehicles"
"Loiter here looking for people"
"Survey the area detecting buildings"
```

**Detection behaviors:**
- `tag_and_continue`: Mark objects, continue mission
- `detect_and_monitor`: Stop and orbit detected objects

---

## License

MIT License

## Support

- **Issues**: https://github.com/yourusername/mav-agent/issues
- **TensorRT-LLM**: https://github.com/NVIDIA/TensorRT-LLM

## Acknowledgments

- [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM)
- [Qwen3-4B-Instruct](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [LangChain](https://github.com/langchain-ai/langchain)
