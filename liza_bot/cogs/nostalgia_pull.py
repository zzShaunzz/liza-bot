import discord
from discord.ext import commands
from discord import app_commands
import datetime
import re

print("[NostalgiaCog] nostalgia_pull.py was imported.")

MAX_CHANNELS = 25
CONTEXT_RANGE = 5  # Number of messages before/after to analyze

class NostalgiaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("[NostalgiaCog] Loaded.")

    @commands.command(name="nostalgiapull")
    async def nostalgiapull_prefix(self, ctx: commands.Context):
        async with ctx.typing():
            await self._run_nostalgia_pull(ctx)

    @app_commands.command(name="nostalgiapull", description="Pull a message from at least a year ago and reflect on it.")
    async def nostalgiapull_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self._run_nostalgia_pull(interaction)

    async def _run_nostalgia_pull(self, source):
        one_year_ago = datetime.datetime.utcnow() - datetime.timedelta(days=365)
        pulled_message = None
        scanned_channels = 0

        for channel in source.guild.text_channels:
            if scanned_channels >= MAX_CHANNELS:
                break
            scanned_channels += 1

            try:
                async for msg in channel.history(oldest_first=True):
                    if msg.created_at < one_year_ago and not msg.author.bot and msg.content:
                        pulled_message = msg
                        break
                if pulled_message:
                    break
            except discord.Forbidden:
                continue

        if not pulled_message:
            if isinstance(source, commands.Context):
                await source.send("😔 Couldn't find any messages older than a year. Try again later!")
            else:
                await source.followup.send("😔 Couldn't find any messages older than a year. Try again later!")
            return

        # Get surrounding messages for context
        context_messages = []
        try:
            async for msg in pulled_message.channel.history(limit=CONTEXT_RANGE * 2, before=pulled_message.created_at, oldest_first=True):
                if not msg.author.bot and msg.content:
                    context_messages.append(msg)
            async for msg in pulled_message.channel.history(limit=CONTEXT_RANGE, after=pulled_message.created_at):
                if not msg.author.bot and msg.content:
                    context_messages.append(msg)
        except discord.Forbidden:
            pass

        context_summary = self.generate_context(pulled_message, context_messages)

        embed = discord.Embed(
            title="📦 Nostalgia Pull",
            description=f"**From:** {pulled_message.author.mention}\n**Channel:** {pulled_message.channel.mention}\n\n{pulled_message.content}",
            timestamp=pulled_message.created_at,
            color=discord.Color.gold()
        )
        embed.set_footer(text="A memory from the past...")

        if isinstance(source, commands.Context):
            await source.send(content=context_summary, embed=embed)
        else:
            await source.followup.send(content=context_summary, embed=embed)

    def generate_context(self, message: discord.Message, surrounding: list[discord.Message]) -> str:
        author = message.author.display_name
        keywords = []
        participants = set()

        for msg in surrounding:
            participants.add(msg.author.display_name)
            keywords.extend(re.findall(r"\b\w+\b", msg.content.lower()))

        keyword_freq = {}
        for word in keywords:
            keyword_freq[word] = keyword_freq.get(word, 0) + 1

        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:3]
        topic = ", ".join([kw for kw, _ in top_keywords]) if top_keywords else "various things"

        if len(participants) > 1:
            return f"🧠 Around this time, {author} was part of a lively discussion involving {', '.join(participants)}. The topic seemed to revolve around {topic}."
        else:
            return f"📜 This message from {author} came during a quiet moment, mostly focused on {topic}."

# Required setup function for cog loading
async def setup(bot):
    await bot.add_cog(NostalgiaCog(bot))
