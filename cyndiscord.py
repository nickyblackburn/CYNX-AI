import os
import discord
import ollama
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
MODEL = os.getenv("OLLAMA_MODEL", "cyn")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Conversation history per channel
history = {}

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Only respond when mentioned or when using !ai
    if not (
        client.user in message.mentions
        or message.content.startswith("!ai")
    ):
        return

    prompt = (
        message.content.replace("!ai", "")
        .replace(f"<@{client.user.id}>", "")
        .strip()
    )

    if not prompt:
        return

    channel = str(message.channel.id)

    if channel not in history:
        history[channel] = []

    history[channel].append({
        "role": "user",
        "content": prompt
    })

    async with message.channel.typing():
        try:
            response = ollama.chat(
                model=MODEL,
                messages=history[channel]
            )

            reply = response["message"]["content"]

            history[channel].append({
                "role": "assistant",
                "content": reply
            })

            # Prevent history from growing forever
            history[channel] = history[channel][-20:]

            # Discord message limit
            for i in range(0, len(reply), 1900):
                await message.channel.send(reply[i:i+1900])

        except Exception as e:
            await message.channel.send(f"Error: {e}")

client.run(TOKEN)