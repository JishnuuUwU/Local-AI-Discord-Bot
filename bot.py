import os
import asyncio
import aiohttp
import discord
from discord.ext import commands
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

# ==========================================
# CONFIGURATION
# ==========================================
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_DISCORD_BOT_TOKEN")
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions")
# Gemma 4 Edge model (sub-5GB VRAM footprint): "gemma4:e2b" or "gemma4:e4b"
MODEL_NAME = os.getenv("MODEL_NAME", "gemma4:e2b")

SYSTEM_PERSONA = (
    "You are OmniClaw, a fast, knowledgeable, and privacy-conscious local AI assistant powered by Gemma 4. "
    "Use provided web context when available. Keep answers clear, technical when relevant, and strictly avoid filler preamble."
)

# ==========================================
# DISCORD CLIENT SETUP
# ==========================================
intents = discord.Intents.default()
intents.message_content = True  # Requires Message Content Intent enabled in developer portal
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# LIGHTWEIGHT CONTEXT SCRAPER
# ==========================================
async def fetch_web_context(query: str, max_results: int = 3) -> str:
    """Lightweight pure-python search scraper pulling DuckDuckGo snippets for real-time grounding."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                if resp.status != 200:
                    return ""
                html = await resp.text()
                
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        for result in soup.find_all("a", class_="result__snippet")[:max_results]:
            text = result.get_text(strip=True)
            if text:
                snippets.append(f"- {text}")
        return "\n".join(snippets)
    except Exception:
        return ""

# ==========================================
# GEMMA 4 LOCAL INFERENCE ENGINE
# ==========================================
async def query_local_gemma(user_prompt: str, context: str = "") -> str:
    """Queries the local OpenAI-compatible endpoint hosting Gemma 4 with bounded resource usage."""
    messages = [{"role": "system", "content": SYSTEM_PERSONA}]
    
    if context:
        user_content = f"[Real-Time Web Context]\n{context}\n\n[User Query]\n{user_prompt}"
    else:
        user_content = user_prompt
        
    messages.append({"role": "user", "content": user_content})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 1024
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(LOCAL_LLM_URL, json=payload, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return raw_text.strip()
                return f"Local inference error: Received HTTP {resp.status} from Ollama backend."
    except asyncio.TimeoutError:
        return "Inference timed out: Local Gemma 4 instance took too long to return tokens."
    except Exception as e:
        return f"Local connection error: Could not reach {LOCAL_LLM_URL} ({e})."

# ==========================================
# BOT EVENT HANDLERS
# ==========================================
@bot.event
async def on_ready():
    print(f"==================================================")
    print(f"Logged in as: {bot.user} (ID: {bot.user.id})")
    print(f"Active Backend Model: {MODEL_NAME}")
    print(f"Endpoint: {LOCAL_LLM_URL}")
    print(f"==================================================")

@bot.event
async def on_message(message: discord.Message):
    # Ignore bot self-messages
    if message.author.bot:
        return

    # Trigger when mentioned or in Direct Messages
    is_mentioned = bot.user in message.mentions
    is_dm = isinstance(message.channel, discord.DMChannel)

    if is_mentioned or is_dm:
        clean_prompt = message.clean_content.replace(f"@{bot.user.name}", "").strip()
        if not clean_prompt:
            return

        async with message.channel.typing():
            # Trigger search scraper on time-sensitive keywords
            search_keywords = ["search", "latest", "today", "news", "current", "what is", "who is", "price of"]
            context = ""
            if any(k in clean_prompt.lower() for k in search_keywords):
                context = await fetch_web_context(clean_prompt)

            reply = await query_local_gemma(clean_prompt, context)

            # Prevent Discord HTTP 400 Bad Request error from empty messages
            if not reply or not reply.strip():
                reply = "The local Gemma 4 model finished inference with an empty output token sequence."

            # Chunking to respect Discord's 2000 character limit
            if len(reply) > 2000:
                for chunk in [reply[i:i+1900] for i in range(0, len(reply), 1900)]:
                    await message.reply(chunk)
            else:
                await message.reply(reply)

    await bot.process_commands(message)

if __name__ == "__main__":
    if DISCORD_TOKEN in ("YOUR_DISCORD_BOT_TOKEN", ""):
        print("ERROR: Set your DISCORD_BOT_TOKEN in environment variables or your .env file.")
        exit(1)
    bot.run(DISCORD_TOKEN)
