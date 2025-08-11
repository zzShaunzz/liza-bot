import discord
from discord.ext import commands
from discord import app_commands
import datetime
import re
import json
import os
import random

print("[NostalgiaCog] nostalgia_pull.py was imported.")

MAX_CHANNELS = 25
LOG_FILE = "nostalgia_log.json"
ALLOWED_CHANNEL_ID = 1399117366926770267  # #bots-general
CONTEXT_TIME_WINDOW = datetime.timedelta(minutes=5)

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
            if isinstance(source, commands.Context):
                await source.send("😔 Couldn't find any new messages older than a year. Try again later!")
            else:
                await source.followup.send("😔 Couldn't find any new messages older than a year. Try again later!")
            return

        pulled_message = random.choice(eligible_messages)
        self.pulled_ids.add(str(pulled_message.id))
        self.save_pulled_ids()

        # Get surrounding messages within ±5 minutes
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

        context_summary = self.generate_context(pulled_message, context_messages)

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
        embed.add_field(name="🔗 Jump to Message", value=f"[Click here to view it]({message_link})", inline=False)
        embed.set_footer(text="A memory from the past...")

        if isinstance(source, commands.Context):
            await source.send(content=context_summary, embed=embed)
        else:
            await source.followup.send(content=context_summary, embed=embed)

    def generate_context(self, message: discord.Message, surrounding: list[discord.Message]) -> str:
        author = message.author.display_name
        participants = {msg.author.display_name for msg in surrounding if msg.author != message.author}
        keywords = []

        for msg in surrounding:
            words = re.findall(r"\b\w+\b", msg.content.lower())
            keywords.extend([w for w in words if len(w) > 3 and not w.startswith("http")])

        keyword_freq = {}
        for word in keywords:
            keyword_freq[word] = keyword_freq.get(word, 0) + 1

        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:3]
        topic = ", ".join([kw for kw, _ in top_keywords]) if top_keywords else "various things"

        if participants:
            return f"🧠 Around this time, {author} was chatting with {', '.join(participants)}. The topic seemed to revolve around {topic}."
        else:
            return f"📜 This message from {author} came during a quiet moment, mostly focused on {topic}."

    def load_pulled_ids(self):
        if not os.path.exists(LOG_FILE):
            return set()
        with open(LOG_FILE, "r") as f:
            return set(json.load(f))

    def save_pulled_ids(self):
        with open(LOG_FILE, "w") as f:
            json.dump(list(self.pulled_ids), f, indent=2)

# Required setup function for cog loading
async def setup(bot):
    await bot.add_cog(NostalgiaCog(bot))
