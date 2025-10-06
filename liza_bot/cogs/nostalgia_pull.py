import discord
from discord.ext import commands
from discord import app_commands
import datetime
import re
import json
import os
import random
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("[NostalgiaCog] nostalgia_pull.py was imported.")

MAX_CHANNELS = 25
LOG_FILE = "nostalgia_log.json"
ALLOWED_CHANNEL_ID = 1399117366926770267  # #bots-general
CONTEXT_TIME_WINDOW = datetime.timedelta(minutes=20)

class JumpToMessageView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__()
        self.add_item(discord.ui.Button(label="Jump to original message", url=url, style=discord.ButtonStyle.link))

class NostalgiaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pulled_ids = self.load_pulled_ids()
        print("[NostalgiaCog] Loaded.")

    @commands.command(name="nostalgiapull")
    async def nostalgiapull_prefix(self, ctx: commands.Context):
        if ctx.channel.id != ALLOWED_CHANNEL_ID:
            await ctx.send("❌ This command can only be used in <#1399117366926770267>.")
            return
        async with ctx.typing():
            await self._run_nostalgia_pull(ctx)

    @app_commands.command(name="nostalgiapull", description="Pull a message from at least a year ago and reflect on it.")
    async def nostalgiapull_slash(self, interaction: discord.Interaction):
        if interaction.channel.id != ALLOWED_CHANNEL_ID:
            await interaction.response.send_message("❌ This command can only be used in <#1399117366926770267>.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        await self._run_nostalgia_pull(interaction)

    async def _run_nostalgia_pull(self, source):
        one_year_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)
        eligible_messages = []
        channels = list(source.guild.text_channels)
        random.shuffle(channels)
        scanned_channels = 0
        for channel in channels:
            if scanned_channels >= MAX_CHANNELS:
                break
            scanned_channels += 1
            try:
                async for msg in channel.history(oldest_first=True):
                    if (
                        msg.created_at < one_year_ago
                        and not msg.author.bot
                        and msg.content
                        and str(msg.id) not in self.pulled_ids
                    ):
                        eligible_messages.append(msg)
            except discord.Forbidden:
                continue
        if not eligible_messages:
            response = "😔 Couldn't find any new messages older than a year. Try again later!"
            if isinstance(source, commands.Context):
                await source.send(response)
            else:
                await source.followup.send(response)
            return
        pulled_message = random.choice(eligible_messages)
        self.pulled_ids.add(str(pulled_message.id))
        self.save_pulled_ids()

        # Generate AI context
        context = await self.generate_ai_context(pulled_message.content)

        # Get surrounding messages within ±20 minutes
        context_messages = []
        try:
            async for msg in pulled_message.channel.history(limit=100, around=pulled_message.created_at):
                if (
                    not msg.author.bot
                    and msg.content
                    and msg.id != pulled_message.id
                    and abs((msg.created_at - pulled_message.created_at)) <= CONTEXT_TIME_WINDOW
                ):
                    context_messages.append(msg)
        except discord.Forbidden:
            pass

        message_link = f"https://discord.com/channels/{pulled_message.guild.id}/{pulled_message.channel.id}/{pulled_message.id}"
        embed = discord.Embed(
            title="📦 Nostalgia Pull",
            description=(
                f"**From:** {pulled_message.author.mention}\n"
                f"**Channel:** {pulled_message.channel.mention}\n\n"
                f"**{pulled_message.content}**"
            ),
            timestamp=pulled_message.created_at,
            color=discord.Color.gold()
        )
        embed.set_footer(text="A memory from the past...")
        view = JumpToMessageView(url=message_link)
        if isinstance(source, commands.Context):
            await source.send(content=context, embed=embed, view=view)
        else:
            await source.followup.send(content=context, embed=embed, view=view)

    async def generate_ai_context(self, message_content):
        """Generate a short AI context using OpenRouter API."""
        api_keys = [
            os.getenv("OPENROUTER_API_KEY_1"),
            os.getenv("OPENROUTER_API_KEY_2"),
            os.getenv("OPENROUTER_API_KEY_3"),
            os.getenv("OPENROUTER_API_KEY_4"),
            os.getenv("OPENROUTER_API_KEY_5"),
            os.getenv("OPENROUTER_API_KEY_6"),
        ]
        api_key = random.choice([key for key in api_keys if key])

        if not api_key:
            return "🤖 No AI context available (API key missing)."

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mistralai/mistral-7b-instruct",
            "messages": [
                {"role": "user", "content": f"Summarize the following message in 10 words or less: '{message_content}'"}
            ],
            "max_tokens": 10
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return f"🤖 {data['choices'][0]['message']['content'].strip()}"
                    else:
                        error = await response.text()
                        logger.error(f"OpenRouter API error: {error}")
                        return "🤖 Failed to generate context."
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "🤖 Failed to generate context."

    def load_pulled_ids(self):
        if not os.path.exists(LOG_FILE):
            return set()
        with open(LOG_FILE, "r") as f:
            return set(json.load(f))

    def save_pulled_ids(self):
        with open(LOG_FILE, "w") as f:
            json.dump(list(self.pulled_ids), f, indent=2)

async def setup(bot):
    await bot.add_cog(NostalgiaCog(bot))
