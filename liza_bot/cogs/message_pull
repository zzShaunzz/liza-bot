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
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("[MessagePullCog] messagepull.py was imported.")

# Configuration
MAX_CHANNELS = 25
MEDIA_LOG_FILE = "messagepull_media_log.json"
TEXT_LOG_FILE = "messagepull_text_log.json"
RANDOM_LOG_FILE = "messagepull_random_log.json"
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

class MessagePullCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.media_pulled_ids = self.load_pulled_ids(MEDIA_LOG_FILE)
        self.text_pulled_ids = self.load_pulled_ids(TEXT_LOG_FILE)
        self.random_pulled_ids = self.load_pulled_ids(RANDOM_LOG_FILE)
        print("[MessagePullCog] Loaded.")

    def load_pulled_ids(self, log_file: str) -> set[str]:
        """Load previously pulled message IDs from a JSON file."""
        if not os.path.exists(log_file):
            return set()
        with open(log_file, "r") as f:
            return set(json.load(f))

    def save_pulled_ids(self, pulled_ids: set[str], log_file: str):
        """Save pulled message IDs to a JSON file."""
        with open(log_file, "w") as f:
            json.dump(list(pulled_ids), f, indent=2)

    def contains_media(self, msg: discord.Message, media_type: Optional[str] = None) -> bool:
        """Check if a message contains media or video."""
        if media_type == "video":
            # Check for video attachments
            for attachment in msg.attachments:
                if attachment.content_type and "video" in attachment.content_type:
                    return True
            # Check for video URLs
            urls = re.findall(r"https?://\S+", msg.content)
            return any("video" in url or "mp4" in url for url in urls)
        else:
            # Check for any media
            if msg.attachments:
                return True
            urls = re.findall(r"https?://\S+", msg.content)
            return any(domain in url for url in urls for domain in MEDIA_DOMAINS)

    async def get_date_threshold(self, date_range: str, months_back: Optional[int] = None) -> datetime.datetime:
        """Calculate the date threshold based on user selection."""
        now = datetime.datetime.now(datetime.timezone.utc)
        
        if date_range == "week":
            return now - datetime.timedelta(days=7)
        elif date_range == "month":
            if months_back is None:
                months_back = 1
            return now - datetime.timedelta(days=30 * months_back)
        elif date_range == "year":
            return now - datetime.timedelta(days=365)
        elif date_range == "six_months":  # For backward compatibility
            return now - datetime.timedelta(days=182)
        else:
            return now - datetime.timedelta(days=365)  # Default to 1 year

    async def find_messages(self, source, pull_type: str, date_range: str, 
                           months_back: Optional[int] = None, 
                           media_type: Optional[str] = None) -> Optional[discord.Message]:
        """Find messages based on criteria."""
        # Calculate the date threshold
        date_threshold = await self.get_date_threshold(date_range, months_back)
        
        # Determine which log to use
        if pull_type == "media":
            log_file = MEDIA_LOG_FILE
            pulled_ids = self.media_pulled_ids
        elif pull_type == "text":
            log_file = TEXT_LOG_FILE
            pulled_ids = self.text_pulled_ids
        else:  # random
            log_file = RANDOM_LOG_FILE
            pulled_ids = self.random_pulled_ids
        
        # For random pulls, don't use date threshold
        if pull_type == "random":
            date_threshold = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        
        eligible_messages = []
        channels = []
        
        # Get appropriate channels
        if pull_type == "media":
            channels = [
                ch for ch in source.guild.text_channels
                if ch.category_id != EXCLUDED_CATEGORY_ID and ch.id not in EXCLUDED_CHANNEL_IDS
            ]
        else:
            channels = list(source.guild.text_channels)
        
        random.shuffle(channels)
        scanned_channels = 0
        
        for channel in channels:
            if scanned_channels >= MAX_CHANNELS:
                break
            scanned_channels += 1
            
            try:
                async for msg in channel.history(oldest_first=True):
                    # Skip if message is too new (except for random pulls)
                    if pull_type != "random" and msg.created_at >= date_threshold:
                        continue
                    
                    # Skip bots
                    if msg.author.bot:
                        continue
                    
                    # Skip already pulled messages
                    if str(msg.id) in pulled_ids:
                        continue
                    
                    # Check message content based on pull type
                    if pull_type == "text":
                        if not msg.content or msg.content.strip() == "":
                            continue
                    elif pull_type == "media":
                        if not self.contains_media(msg, media_type):
                            continue
                    elif pull_type == "random":
                        if not msg.content or msg.content.strip() == "":
                            continue
                    
                    eligible_messages.append((msg, pulled_ids, log_file))
                    
            except discord.Forbidden:
                continue
        
        if not eligible_messages:
            return None, None, None
        
        # Select random message and return with its associated log info
        pulled_message, pulled_ids, log_file = random.choice(eligible_messages)
        return pulled_message, pulled_ids, log_file

    @app_commands.command(name="messagepull", description="Pull a message from the server based on your preferences.")
    async def messagepull_slash(self, interaction: discord.Interaction):
        """Main slash command for message pulling."""
        if interaction.channel.id != ALLOWED_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ This command can only be used in <#1399117366926770267>.", 
                ephemeral=True
            )
            return
        
        # Create dropdown for pull type
        class PullTypeSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="Media Pull", value="media", description="Pull messages with images/videos"),
                    discord.SelectOption(label="Text Pull", value="text", description="Pull text-only messages"),
                    discord.SelectOption(label="Random Pull", value="random", description="Pull any random message")
                ]
                super().__init__(placeholder="Choose the type of pull...", options=options)
            
            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer(thinking=False)
                pull_type = self.values[0]
                
                # Create dropdown for date range
                class DateRangeSelect(discord.ui.Select):
                    def __init__(self, pull_type: str):
                        options = [
                            discord.SelectOption(label="Older than a week", value="week"),
                            discord.SelectOption(label="Older than a month", value="month"),
                            discord.SelectOption(label="Older than a year", value="year")
                        ]
                        if pull_type == "random":
                            options = [
                                discord.SelectOption(label="Any time (random)", value="any")
                            ]
                        super().__init__(placeholder="Choose date range...", options=options)
                        self.pull_type = pull_type
                    
                    async def callback(self, interaction: discord.Interaction):
                        date_range = self.values[0]
                        months_back = None
                        
                        # If month is selected, ask for number of months
                        if date_range == "month" and self.pull_type != "random":
                            await interaction.response.send_message(
                                "How many months back would you like to pull from? (Enter a number, e.g., 3 for 3 months):",
                                ephemeral=True
                            )
                            
                            def check(m):
                                return m.author == interaction.user and m.channel == interaction.channel
                            
                            try:
                                msg = await self.view.bot.wait_for('message', timeout=30.0, check=check)
                                if msg.content.isdigit():
                                    months_back = int(msg.content)
                                    if months_back < 1:
                                        months_back = 1
                                    if months_back > 120:  # 10 year limit
                                        months_back = 120
                                else:
                                    await interaction.followup.send("Invalid input. Using default of 1 month.", ephemeral=True)
                                    months_back = 1
                            except TimeoutError:
                                await interaction.followup.send("Timed out. Using default of 1 month.", ephemeral=True)
                                months_back = 1
                        
                        # For random pulls, set date_range to None
                        if self.pull_type == "random":
                            date_range = "any"
                        
                        # If media pull, ask for media type
                        media_type = None
                        if self.pull_type == "media":
                            class MediaTypeSelect(discord.ui.Select):
                                def __init__(self):
                                    options = [
                                        discord.SelectOption(label="Any Media", value="any", description="Images, videos, etc."),
                                        discord.SelectOption(label="Video Only", value="video", description="Videos only")
                                    ]
                                    super().__init__(placeholder="Choose media type...", options=options)
                                
                                async def callback(self, interaction: discord.Interaction):
                                    media_type = self.values[0]
                                    if media_type == "any":
                                        media_type = None
                                    
                                    # Now execute the pull
                                    await interaction.response.defer(thinking=True)
                                    await self.view.execute_pull(
                                        interaction, 
                                        self.view.pull_type, 
                                        date_range, 
                                        months_back, 
                                        media_type
                                    )
                            
                            view = discord.ui.View()
                            view.add_item(MediaTypeSelect())
                            view.bot = self.view.bot
                            view.pull_type = self.pull_type
                            view.execute_pull = self.view.execute_pull
                            
                            await interaction.followup.send(
                                "Choose the type of media you want to pull:", 
                                view=view, 
                                ephemeral=True
                            )
                            return
                        
                        # For non-media pulls, execute directly
                        await interaction.response.defer(thinking=True)
                        await self.view.execute_pull(
                            interaction, 
                            self.pull_type, 
                            date_range, 
                            months_back, 
                            media_type
                        )
                
                # Create view for date range selection
                date_view = discord.ui.View()
                date_view.add_item(DateRangeSelect(pull_type))
                date_view.bot = self.view.bot
                date_view.pull_type = pull_type
                date_view.execute_pull = self.view.execute_pull
                
                await interaction.followup.send(
                    "Choose how old you want the message to be:", 
                    view=date_view, 
                    ephemeral=True
                )
        
        # Create initial view
        view = discord.ui.View()
        view.add_item(PullTypeSelect())
        view.bot = self.bot
        view.execute_pull = self.execute_pull
        
        await interaction.response.send_message(
            "Welcome to Message Pull! What type of message would you like to pull?",
            view=view,
            ephemeral=True
        )

    async def execute_pull(self, interaction: discord.Interaction, pull_type: str, 
                          date_range: str, months_back: Optional[int] = None,
                          media_type: Optional[str] = None):
        """Execute the actual message pull."""
        # Find a message
        pulled_message, pulled_ids, log_file = await self.find_messages(
            interaction, pull_type, date_range, months_back, media_type
        )
        
        if not pulled_message:
            response = "😔 Couldn't find any messages matching your criteria."
            await interaction.followup.send(response)
            return
        
        # Add to pulled IDs
        pulled_ids.add(str(pulled_message.id))
        
        # Save to appropriate log file
        if pull_type == "media":
            self.save_pulled_ids(pulled_ids, MEDIA_LOG_FILE)
        elif pull_type == "text":
            self.save_pulled_ids(pulled_ids, TEXT_LOG_FILE)
        else:
            self.save_pulled_ids(pulled_ids, RANDOM_LOG_FILE)
        
        # Create embed
        message_link = f"https://discord.com/channels/{pulled_message.guild.id}/{pulled_message.channel.id}/{pulled_message.id}"
        
        # Determine embed title and color based on pull type
        if pull_type == "media":
            title = "🎞️ Media Pull"
            color = discord.Color.blue()
            footer = "A visual memory from the past..."
        elif pull_type == "text":
            title = "📦 Text Pull"
            color = discord.Color.gold()
            footer = "A written memory from the past..."
        else:
            title = "🎲 Random Pull"
            color = discord.Color.purple()
            footer = "A random moment from the server..."
        
        embed = discord.Embed(
            title=title,
            description=(
                f"**From:** {pulled_message.author.mention}\n"
                f"**Channel:** {pulled_message.channel.mention}\n"
                f"**Date:** {pulled_message.created_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"{pulled_message.content or '[Media message with no text]'}"
            ),
            timestamp=pulled_message.created_at,
            color=color
        )
        embed.set_footer(text=footer)
        
        # Add media if present
        if pulled_message.attachments:
            first_attachment = pulled_message.attachments[0]
            if first_attachment.content_type and "image" in first_attachment.content_type:
                embed.set_image(url=first_attachment.url)
            elif first_attachment.content_type and "video" in first_attachment.content_type:
                video_url = first_attachment.url
                await interaction.followup.send(video_url)
        
        # Check for media URLs in content
        elif pulled_message.content:
            urls = re.findall(r"https?://\S+", pulled_message.content)
            for url in urls:
                if any(domain in url for domain in MEDIA_DOMAINS):
                    embed.set_image(url=url)
                    break
        
        # Add author avatar
        if pulled_message.author.avatar:
            embed.set_author(name=pulled_message.author.display_name, icon_url=pulled_message.author.avatar.url)
        
        view = JumpToMessageView(url=message_link)
        await interaction.followup.send(embed=embed, view=view)

    # Prefix commands for backward compatibility
    @commands.command(name="messagepull")
    async def messagepull_prefix(self, ctx: commands.Context):
        """Prefix command version that redirects to slash command instructions."""
        if ctx.channel.id != ALLOWED_CHANNEL_ID:
            await ctx.send("❌ This command can only be used in <#1399117366926770267>.")
            return
        
        await ctx.send("Please use the slash command `/messagepull` for interactive message pulling.")

async def setup(bot: commands.Bot):
    await bot.add_cog(MessagePullCog(bot))
