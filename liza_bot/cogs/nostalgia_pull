import discord
from discord.ext import commands
import datetime
import re

print("[NostalgiaCog] nostalgia_pull.py was imported.")

MAX_CHANNELS = 25  # ✅ Safety cap to avoid scanning too many channels

class NostalgiaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("[NostalgiaCog] Loaded.")

    @commands.command(name="nostalgiapull")
    async def nostalgiapull(self, ctx: commands.Context):
        await ctx.trigger_typing()

        one_year_ago = datetime.datetime.utcnow() - datetime.timedelta(days=365)
        pulled_message = None
        scanned_channels = 0

        for channel in ctx.guild.text_channels:
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
                continue  # Skip channels the bot can't access

        if not pulled_message:
            await ctx.send("😔 Couldn't find any messages older than a year. Try again later!")
            return

        # Generate a dynamic context description
        context_summary = self.generate_context(pulled_message)

        embed = discord.Embed(
            title="📦 Nostalgia Pull",
            description=f"**From:** {pulled_message.author.mention}\n**Channel:** {pulled_message.channel.mention}\n\n{pulled_message.content}",
            timestamp=pulled_message.created_at,
            color=discord.Color.gold()
        )
        embed.set_footer(text="A memory from the past...")

        await ctx.send(content=context_summary, embed=embed)

    def generate_context(self, message: discord.Message) -> str:
        content = message.content.strip()

        # Detect question
        if "?" in content:
            return f"❓ Back then, {message.author.display_name} was asking a question — maybe looking for help or sparking a discussion."

        # Detect announcement-style message
        if re.match(r"^(hey|attention|announcement|update)\b", content.lower()):
            return f"📢 This looks like an announcement or update from {message.author.display_name}. Something important was going on."

        # Detect laughter or jokes
        if any(word in content.lower() for word in ["lol", "lmao", "😂", "🤣", "haha"]):
            return f"😄 A funny moment from the past — {message.author.display_name} had the server laughing!"

        # Detect gaming or media
        if any(word in content.lower() for word in ["game", "match", "movie", "episode", "stream"]):
            return f"🎮 This message was part of a chat about games or media. {message.author.display_name} was sharing or reacting to something fun."

        # Detect emotional tone
        if any(word in content.lower() for word in ["miss", "remember", "nostalgic", "sad", "happy", "excited"]):
            return f"💭 A heartfelt message from {message.author.display_name} — emotions were running high in this moment."

        # Fallback: summarize based on length and tone
        if len(content.split()) < 6:
            return f"🗣️ A short message from {message.author.display_name}, but it still captured a slice of server history."
        else:
            return f"📜 A snapshot of conversation from long ago — {message.author.display_name} was sharing something meaningful."

# Required setup function for cog loading
async def setup(bot):
    await bot.add_cog(NostalgiaCog(bot))
