import discord
from discord.ext import commands
from discord import app_commands
import re, random, requests, os, json
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

BOT_CHANNEL_ID = 1271294510164607008  # Original Liza channel
COMMAND_CHANNEL_ID = 1451423055426355220  # New channel for !lizaai command
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("MODEL", "anthropic/claude-3.5-sonnet")  # Add default model

class LizaAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("[LizaAI] Cog initialized!")
        print(f"[LizaAI] Listening in channels: {BOT_CHANNEL_ID} (mentions) and {COMMAND_CHANNEL_ID} (!lizaai)")

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
            f"User {username} said: \"{message_content}\"\n\n"
            f"Reply in a creative toddler voice using silly logic, giggles, and made-up words. Replies should feel spontaneous and different every time."
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Handle mentions in the original bot channel
        if message.channel.id == BOT_CHANNEL_ID:
            print(f"📨 Message received in Liza's channel {message.channel.id}: {message.content}")

            if message.mention_everyone or self.bot.user in message.mentions or re.search(r"\bliza\b", message.content, re.IGNORECASE):
                print("🎯 Liza was mentioned in her channel!")
                await self.generate_liza_response(message)
        
        # Handle !lizaai command in the command channel
        elif message.channel.id == COMMAND_CHANNEL_ID and message.content.startswith("!lizaai"):
            print(f"📨 !lizaai command received in channel {message.channel.id}: {message.content}")
            await self.handle_lizaai_command(message)

        await self.bot.process_commands(message)

    async def generate_liza_response(self, message):
        """Generate Liza's response to a message"""
        # Select a random API key
        api_keys = [key for key in OPENROUTER_API_KEYS if key]
        if not api_keys:
            print("❌ No API keys found!")
            await message.channel.send("Liza's juice box is empty! No API keys found. 😢")
            return

        api_key = random.choice(api_keys)
        print(f"🔑 Using API key (first 10 chars): {api_key[:10]}...")

        try:
            prompt = self.liza_personality(message.content, message.author.display_name)
            print(f"📝 Prompt length: {len(prompt)} chars")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://discord.com",  # OpenRouter requires this
                "X-Title": "Liza Toddler Bot"  # OpenRouter requires this
            }
            payload = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 1.3,
                "top_p": 0.9,
                "max_tokens": 140
            }
            
            print(f"🚀 Sending request to OpenRouter...")
            print(f"📦 Model: {MODEL}")
            
            response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
            print(f"📡 Response status: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                liza_reply = data["choices"][0]["message"]["content"].strip()
                print(f"💬 Liza's reply: {liza_reply}")
                await message.channel.send(liza_reply)
            else:
                print(f"❌ No choices in response: {data}")
                await message.channel.send("Liza got confused and started babbling nonsense! 🍼")
                
        except requests.exceptions.Timeout:
            print("⏰ Request timed out!")
            await message.channel.send("Liza got distracted by a butterfly and forgot what she was saying! 🦋")
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            if hasattr(e, 'response') and e.response:
                if e.response.status_code == 401:
                    await message.channel.send("Liza's juice box key doesn't work! (Invalid API key) 🔑")
                elif e.response.status_code == 429:
                    await message.channel.send("Liza drank too much juice too fast! (Rate limited) 🚰")
                elif e.response.status_code == 400:
                    await message.channel.send("Liza mixed up her words! (Bad request) 🤪")
                else:
                    await message.channel.send(f"Liza spilled her juice! (Error {e.response.status_code}) 😢")
            else:
                await message.channel.send("Liza spilled her juice and can't talk 😢")
        except Exception as e:
            print(f"❌ Unexpected error: {type(e).__name__}: {e}")
            await message.channel.send("Liza got tangled in her blanket and needs help! 🐻")

    async def handle_lizaai_command(self, message):
        """Handle the !lizaai command in the command channel"""
        # Extract the user's message after the command
        command_parts = message.content.split(" ", 1)
        if len(command_parts) < 2:
            await message.channel.send("Heehee! Liza needs something to giggle about! Try: `!lizaai [your message]` 🍭")
            return
        
        user_message = command_parts[1].strip()
        if not user_message:
            await message.channel.send("Heehee! Liza heard whispers but no words! Say something fun! 🎈")
            return
        
        print(f"💬 Processing !lizaai command with message: {user_message}")
        
        # Show typing indicator
        async with message.channel.typing():
            # Select a random API key
            api_keys = [key for key in OPENROUTER_API_KEYS if key]
            if not api_keys:
                await message.channel.send("Liza's juice box is empty! No API keys found. 😢")
                return

            api_key = random.choice(api_keys)
            
            try:
                # Create a prompt for the command channel
                prompt = self.liza_personality(user_message, message.author.display_name)
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://discord.com",
                    "X-Title": "Liza Toddler Bot"
                }
                payload = {
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 1.3,
                    "top_p": 0.9,
                    "max_tokens": 140
                }
                
                response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    liza_reply = data["choices"][0]["message"]["content"].strip()
                    await message.channel.send(liza_reply)
                else:
                    await message.channel.send("Liza got confused and started babbling nonsense! 🍼")
                    
            except requests.exceptions.Timeout:
                await message.channel.send("Liza got distracted by a butterfly and forgot what she was saying! 🦋")
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response:
                    if e.response.status_code == 401:
                        await message.channel.send("Liza's juice box key doesn't work! (Invalid API key) 🔑")
                    elif e.response.status_code == 429:
                        await message.channel.send("Liza drank too much juice too fast! (Rate limited) 🚰")
                    else:
                        await message.channel.send("Liza spilled her juice! 😢")
                else:
                    await message.channel.send("Liza spilled her juice and can't talk 😢")
            except Exception as e:
                print(f"❌ Error in !lizaai command: {e}")
                await message.channel.send("Liza got tangled in her blanket and needs help! 🐻")

    @app_commands.command(name="response", description="Check if Liza is listening in her channel")
    async def response(self, interaction: discord.Interaction):
        if interaction.channel.id != BOT_CHANNEL_ID:
            await interaction.response.send_message("Liza only listens in her special playroom! 🏠", ephemeral=True)
            return
        
        # Test the API connection
        api_keys = [key for key in OPENROUTER_API_KEYS if key]
        if not api_keys:
            await interaction.response.send_message("❌ Liza's juice boxes are all empty!", ephemeral=True)
            return
            
        await interaction.response.send_message("Heehee! Liza hears you loud and giggly! 🍭✨")

    @commands.command(name="testliza")
    async def test_liza(self, ctx):
        """Test Liza's API connection"""
        api_keys = [key for key in OPENROUTER_API_KEYS if key]
        await ctx.send(f"🍭 Liza has {len(api_keys)} juice boxes ready!")
        
        # Test the simplest possible request
        if api_keys:
            try:
                test_key = api_keys[0]
                headers = {
                    "Authorization": f"Bearer {test_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://discord.com",
                    "X-Title": "Liza Toddler Bot"
                }
                test_payload = {
                    "model": MODEL,
                    "messages": [{"role": "user", "content": "Say 'Hello Liza!'"}],
                    "max_tokens": 10
                }
                
                test_response = requests.post(OPENROUTER_URL, headers=headers, json=test_payload, timeout=10)
                if test_response.status_code == 200:
                    await ctx.send("✅ Liza's juice boxes are working!")
                else:
                    await ctx.send(f"❌ Juice box test failed: {test_response.status_code}")
            except Exception as e:
                await ctx.send(f"❌ Juice box test error: {e}")

    @commands.command(name="lizaai", aliases=["liza"])
    async def lizaai_command(self, ctx, *, message: str):
        """Talk to Liza AI with a command"""
        # Check if we're in the allowed channel
        if ctx.channel.id != COMMAND_CHANNEL_ID:
            await ctx.send(f"Liza only plays in her command room! Go to <#{COMMAND_CHANNEL_ID}> 🏠")
            return
        
        print(f"🎯 !lizaai command from {ctx.author}: {message}")
        
        # Call the same handler used for on_message
        fake_message = type('obj', (object,), {
            'channel': ctx.channel,
            'author': ctx.author,
            'content': f"!lizaai {message}"
        })()
        
        await self.handle_lizaai_command(fake_message)

async def setup(bot):
    await bot.add_cog(LizaAI(bot))
    print("[LizaAI] ✅ Cog loaded successfully!")
