import discord
from discord.ext import commands
from discord import app_commands
import datetime
import re
import json
import os
import random

print("[NostalgiaMediaCog] nostalgia_media.py was imported.")

MAX_CHANNELS = 25
LOG_FILE = "nostalgia_media_log.json"
ALLOWED_CHANNEL_ID = 1399117366926770267  # #bots-general
EXCLUDED_CATEGORY_ID = 1265093508595843193
EXCLUDED_CHANNEL_IDS = {1398892088984076368}  # starboard
CONTEXT_TIME_WINDOW = datetime.timedelta(minutes=20)

MEDIA_DOMAINS = [
    "drive.google.com", "photos.google.com", "imgur.com",
    "tenor.com", "giphy.com", "media.discordapp.net", "cdn.discordapp.com"
]

class JumpToMessageView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__()
        self.add_item(discord.ui.Button(label="Jump to Message", url=url, style=discord.ButtonStyle.link))

class NostalgiaMediaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pulled_ids = self.load_pulled_ids()
        print("[NostalgiaMediaCog] Loaded.")

    @commands.command(name="nostalgiamedia")
    async def nostalgiamedia_prefix(self, ctx: commands.Context):
        if ctx.channel.id != ALLOWED_CHANNEL_ID:
            await ctx.send("❌ This command can only be used in <#1399117366926770267>.")
            return
        async with ctx.typing():
            await self._run_nostalgia_media(ctx)

    @app_commands.command(name="nostalgiamedia", description="Pull a media message from at least 6 months ago.")
    async def nostalgiamedia_slash(self, interaction: discord.Interaction):
        if interaction.channel.id != ALLOWED_CHANNEL_ID:
            await interaction.response.send_message("❌ This command can only be used in <#1399117366926770267>.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        await self._run_nostalgia_media(interaction)

    @commands.command(name="nostalgiavideo")
    async def nostalgiavideo_prefix(self, ctx: commands.Context):
        if ctx.channel.id != ALLOWED_CHANNEL_ID:
            await ctx.send("❌ This command can only be used in <#1399117366926770267>.")
            return
        async with ctx.typing():
            await self._run_nostalgia_media(ctx, media_type="video")

    @app_commands.command(name="nostalgiavideo", description="Pull a video message from at least 6 months ago.")
    async def nostalgiavideo_slash(self, interaction: discord.Interaction):
        if interaction.channel.id != ALLOWED_CHANNEL_ID:
            await interaction.response.send_message("❌ This command can only be used in <#1399117366926770267>.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        await self._run_nostalgia_media(interaction, media_type="video")

    async def _run_nostalgia_media(self, source, media_type=None):
        six_months_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=182)
        eligible_messages = []

        channels = [
            ch for ch in source.guild.text_channels
            if ch.category_id != EXCLUDED_CATEGORY_ID and ch.id not in EXCLUDED_CHANNEL_IDS
        ]
        random.shuffle(channels)
        scanned_channels = 0

        for channel in channels:
            if scanned_channels >= MAX_CHANNELS:
                break
            scanned_channels += 1

            try:
                async for msg in channel.history(oldest_first=True):
                    if (
                        msg.created_at < six_months_ago
                        and not msg.author.bot
                        and str(msg.id) not in self.pulled_ids
                        and self.contains_media(msg, media_type)
                    ):
                        eligible_messages.append(msg)
            except discord.Forbidden:
                continue

        if not eligible_messages:
            response = "😔 Couldn't find any media messages older than 6 months."
            if isinstance(source, commands.Context):
                await source.send(response)
            else:
                await source.followup.send(response)
            return

        pulled_message = random.choice(eligible_messages)
        self.pulled_ids.add(str(pulled_message.id))
        self.save_pulled_ids()

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
            title="🎞️ Nostalgia Media Pull",
            description=(
                f"**From:** {pulled_message.author.mention}\n"
                f"**Channel:** {pulled_message.channel.mention}\n\n"
                f"**{pulled_message.content or '[Media message with no text]'}**"
            ),
            timestamp=pulled_message.created_at,
            color=discord.Color.blue()
        )
        embed.set_footer(text="A visual memory from the past...")

        if pulled_message.attachments:
            first_attachment = pulled_message.attachments[0]
            if first_attachment.content_type and "image" in first_attachment.content_type:
                embed.set_image(url=first_attachment.url)
            elif first_attachment.content_type and "video" in first_attachment.content_type:
                embed.set_video(url=first_attachment.url)
        elif pulled_message.content:
            urls = re.findall(r"https?://\S+", pulled_message.content)
            for url in urls:
                if any(domain in url for domain in MEDIA_DOMAINS):
                    embed.set_image(url=url)
                    break

        view = JumpToMessageView(url=message_link)

        if isinstance(source, commands.Context):
            await source.send(content=context_summary, embed=embed, view=view)
        else:
            await source.followup.send(content=context_summary, embed=embed, view=view)

    def contains_media(self, msg: discord.Message, media_type=None) -> bool:
        if media_type == "video":
            for attachment in msg.attachments:
                if attachment.content_type and "video" in attachment.content_type:
                    return True
            urls = re.findall(r"https?://\S+", msg.content)
            return any("video" in url or "mp4" in url for url in urls)
        else:
            if msg.attachments:
                return True
            urls = re.findall(r"https?://\S+", msg.content)
            return any(domain in url for url in urls for domain in MEDIA_DOMAINS)

    def generate_context(self, message: discord.Message, surrounding: list[discord.Message]) -> str:
        author = message.author.display_name
        participants = {msg.author.display_name for msg in surrounding if msg.author != message.author}
        keywords = []

        for msg in surrounding:
            cleaned = re.sub(r"<a?:\w+:\d+>", "", msg.content)
            cleaned = re.sub(r"https?://\S+", "", cleaned)
            cleaned = re.sub(r"<@\d+>", "", cleaned)
            cleaned = re.sub(r"\b\d{6,}\b", "", cleaned)
            words = re.findall(r"\b\w+\b", cleaned.lower())
            keywords.extend([w for w in words if len(w) > 3])

        keyword_freq = {}
        for word in keywords:
            keyword_freq[word] = keyword_freq.get(word, 0) + 1

        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:3]
        topic = ", ".join([kw for kw, _ in top_keywords])

        if participants and topic:
            return f"🧠 Around this time, {author} was sharing media with {', '.join(participants)} about {topic}."
        elif participants:
            return f"🧠 {author} was part of a media exchange with {', '.join(participants)}."
        elif topic:
            return f"📸 This media message from {author} was part of a moment focused on {topic}."
        else:
            return f"📸 A quiet media moment from {author}, with little else around it."

    def load_pulled_ids(self):
        if not os.path.exists(LOG_FILE):
            return set()
        with open(LOG_FILE, "r") as f:
            return set(json.load(f))

    def save_pulled_ids(self):
        with open(LOG_FILE, "w") as f:
            json.dump(list(self.pulled_ids), f, indent=2)

async def setup(bot: commands.Bot):
    await bot.add_cog(NostalgiaMediaCog(bot))
