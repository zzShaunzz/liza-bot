import discord
from discord.ext import commands
from discord import app_commands  # Required for hybrid commands
import random
import aiohttp
import os
import logging
import datetime
import re
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOG_FILE = "randompull_log.json"

class JumpToMessageView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__()
        self.add_item(discord.ui.Button(label="Jump to original message", url=url, style=discord.ButtonStyle.link))

class RandomPull(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pulled_ids = self.load_pulled_ids()
        logger.info("[RandomPullCog] Loaded.")

    @commands.command(name="randompull")
    async def randompull_prefix(self, ctx: commands.Context):
        async with ctx.typing():
            await self._run_random_pull(ctx)

    @app_commands.command(name="randompull", description="Pull a random message from the server and reflect on it.")
    async def randompull_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self._run_random_pull(interaction)

    async def _run_random_pull(self, source):
        channels = list(source.guild.text_channels)
        random.shuffle(channels)

        eligible_messages = []
        for channel in channels:
            try:
                async for msg in channel.history(limit=100):
                    if (
                        not msg.author.bot
                        and msg.content
                        and str(msg.id) not in self.pulled_ids
                    ):
                        eligible_messages.append(msg)
            except discord.Forbidden:
                continue

        if not eligible_messages:
            response = "😔 Couldn't find any messages to pull. Try again later!"
            if isinstance(source, commands.Context):
                await source.send(response)
            else:
                await source.followup.send(response)
            return

        pulled_message = random.choice(eligible_messages)
        self.pulled_ids.add(str(pulled_message.id))
        self.save_pulled_ids()

        context = await self.generate_ai_context(pulled_message.content)

        message_link = f"https://discord.com/channels/{pulled_message.guild.id}/{pulled_message.channel.id}/{pulled_message.id}"

        embed = discord.Embed(
            title="🎲 Random Message Pull",
            description=(
                f"**From:** {pulled_message.author.mention}\n"
                f"**Channel:** {pulled_message.channel.mention}\n\n"
                f"**{pulled_message.content}**"
            ),
            timestamp=pulled_message.created_at,
            color=discord.Color.blue()
        )
        embed.set_footer(text="A random moment from the server...")

        view = JumpToMessageView(url=message_link)
        if isinstance(source, commands.Context):
            await source.send(content=context, embed=embed, view=view)
        else:
            await source.followup.send(content=context, embed=embed, view=view)

    async def generate_ai_context(self, message_content):
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
    await bot.add_cog(RandomPull(bot))
