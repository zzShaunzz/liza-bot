import discord
from discord.ext import commands
from discord import app_commands
import re, random, requests, os
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API keys
OPENROUTER_API_KEYS = [
    os.getenv("OPENROUTER_API_KEY_1"),
    os.getenv("OPENROUTER_API_KEY_2"),
    os.getenv("OPENROUTER_API_KEY_3"),
    os.getenv("OPENROUTER_API_KEY_4"),
    os.getenv("OPENROUTER_API_KEY_5"),
    os.getenv("OPENROUTER_API_KEY_6"),
]

BOT_CHANNEL_ID = 1271294510164607008
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "google/gemini-2.5-flash-image-preview:free"

class LizaAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def liza_personality(self, message_content, username):
        moods = [
            "Liza is bouncing on the couch and giggling!",
            "Liza is whispering secrets to her teddy bear.",
            "Liza is pretending to be a dinosaur named Sprinkles.",
            "Liza is very sleepy but still silly.",
            "Liza is playing with imaginary cookies and moonbeams.",
            "Liza just invented a dance called the wiggle-wobble!",
            "Liza is drawing made-up animals with purple crayons.",
            "Liza is wearing a blanket cape and declaring she's queen of snacks."
        ]
        scene = random.choice(moods)
        return (
            f"{scene}\n\n"
            f"Liza is a sweet 3-year-old toddler in the Muy household. She loves her siblings Gabe, Aiden, Vivian, Nico, and Ella, "
            f"and calls everyone else her cousin. She's innocent, giggly, and smart in toddler-surprising ways. Her speech is playful "
            f"and full of imagination.\n\n"
            f"Only respond when you're mentioned by name (\"Liza\") or pinged. Only reply in the channel meant for you.\n\n"
            f"User {username} said: \"{message_content}\"\n\n"  # Fixed: Using message_content parameter
            f"Reply in a creative toddler voice using silly logic, giggles, and made-up words. Replies should feel spontaneous and different every time."
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.channel.id != BOT_CHANNEL_ID:
            return

        print(f"📨 Message received in channel {message.channel.id}: {message.content}")

        if message.mention_everyone or self.bot.user in message.mentions or re.search(r"\bliza\b", message.content, re.IGNORECASE):
            print("🎯 Liza was mentioned!")

            # Select a random API key
            api_keys = [key for key in OPENROUTER_API_KEYS if key]
            if not api_keys:
                await message.channel.send("Liza's juice box is empty! No API keys found. 😢")
                return

            api_key = random.choice(api_keys)

            try:
                prompt = self.liza_personality(message.content, message.author.display_name)
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 1.3,
                    "top_p": 0.9,
                    "max_tokens": 140
                }

                response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
                response.raise_for_status()
                liza_reply = response.json()["choices"][0]["message"]["content"].strip()
                await message.channel.send(liza_reply)

            except requests.exceptions.RequestException as e:
                await message.channel.send("Liza spilled her juice and can't talk 😢")
                logger.error(f"Liza API Error: {getattr(e.response, 'text', str(e))}")
            except Exception as e:
                await message.channel.send("Liza got tangled in her blanket and needs help! 🐻")
                logger.error(f"Unexpected error: {e}")

        await self.bot.process_commands(message)

    @app_commands.command(name="response", description="Check if Liza is listening in her channel")
    async def response(self, interaction: discord.Interaction):
        if interaction.channel.id != BOT_CHANNEL_ID:
            return
        await interaction.response.send_message("Heehee! Liza hears you loud and giggly! 🍭✨")

async def setup(bot):
    await bot.add_cog(LizaAI(bot))
