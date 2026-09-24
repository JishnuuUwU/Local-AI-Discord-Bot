# OmniClaw Discord Bot (Local AI with Gemma 4)

A lightweight, privacy-first Discord bot powered by Google DeepMind's open-weight **Gemma 4** architecture. Built with `discord.py` and optimized to run entirely on consumer hardware (sub-5GB VRAM) via Ollama or local OpenAI-compatible inference backends.

Includes an integrated, zero-API-key Python web search scraper to inject real-time context on demand.

---

## Features

* **Local Inference with Gemma 4**: Runs on edge-optimized Gemma 4 variants (`gemma4:e2b` or `gemma4:e4b`) with zero cloud dependencies or per-token fees.
* **Low VRAM Footprint**: Tuned for laptops and low-VRAM GPUs (~2.9GB–4.5GB VRAM footprint with Q4 quantization).
* **Lightweight Context Ingestion**: Built-in DuckDuckGo HTML scraping layer that pulls top web snippets for time-sensitive prompts without heavy scraping frameworks.
* **Robust Discord Handling**: Enforces automatic message chunking for replies >2000 characters and guards against Discord HTTP 400 Bad Request errors on empty generation outputs.
* **Fully Asynchronous**: Built entirely on `asyncio` and `aiohttp` for non-blocking local generation.

---

## Prerequisites

1. **Python 3.10+**
2. **Ollama** (or any local server providing an OpenAI-compatible API)
3. **Discord Bot Token** (from the Discord Developer Portal)

---

## Quickstart

### 1. Install and Pull Gemma 4

Ensure Ollama is running, then pull the Gemma 4 edge model:

```bash
# E2B variant (~2.9 GB VRAM footprint - best for lower specs)
ollama run gemma4:e2b

# Or the E4B variant (~4.5 GB VRAM footprint - higher reasoning power)
ollama run gemma4:e4b

```

Verify that the local OpenAI-compatible endpoint is live at `http://localhost:11434/v1`.

### 2. Clone the Repository & Install Dependencies

```bash
git clone https://github.com/<your-username>/omniclaw-bot.git
cd omniclaw-bot

python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

```

### 3. Environment Configuration

Create a `.env` file in the root directory:

```env
DISCORD_BOT_TOKEN=your_actual_discord_bot_token_here
LOCAL_LLM_URL=http://localhost:11434/v1/chat/completions
MODEL_NAME=gemma4:e2b

```

> **Note:** Make sure **Privileged Gateway Intents** (`MESSAGE CONTENT INTENT`) are enabled in your Discord Developer Portal application settings under the **Bot** tab.

### 4. Run the Bot

```bash
python bot.py

```

---

## Project Structure

```text
├── bot.py             # Main Discord client, context scraper, and inference logic
├── requirements.txt   # Python dependencies
├── .env.example       # Template environment variables
└── README.md          # Documentation and hardware setup

```

---

## Configuration Reference

| Variable | Default | Description |
| --- | --- | --- |
| `DISCORD_BOT_TOKEN` | *None* | Bot token obtained from the Discord Developer Portal |
| `LOCAL_LLM_URL` | `http://localhost:11434/v1/chat/completions` | Local inference endpoint (Ollama, vLLM, LM Studio) |
| `MODEL_NAME` | `gemma4:e2b` | Target local model identifier (`gemma4:e2b`, `gemma4:e4b`) |

---

## License

This project is licensed under the Apache-2.0 License — matching the Gemma 4 open model license.
