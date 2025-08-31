import discord
from discord.ext import commands
from discord import app_commands
import re, asyncio, hashlib, os
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
import sys

# 🔒 Load token
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN is missing.")
    exit()

# 🌐 Flask keep_alive
app = Flask("keep_alive")

@app.route("/")
def home():
    return "Bot is alive!"

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# 🤖 Bot & Intents
intents = discord.Intents.default()
intents.message_content = intents.messages = intents.reactions = intents.guilds = True
intents.members = True  # 🔥 Required for fetch_members and role audits
bot = commands.Bot(command_prefix=["!", "/"], intents=intents)
tree = bot.tree

# 🔧 Configs
SOURCE_CHANNEL_ID = 1196349674139963485
TARGET_CHANNEL_ID = 1398892088984076368
TROUBLESHOOT_CHANNEL_ID = 1399117366926770267
STARBOARD_CHANNEL_ID = 123456789012345678  # Replace with your actual starboard channel ID
TRIGGER_EMOJI = "⭐"
HEART_EMOJIS = ["❤️","🧡","💛","💚","💙","💜","🖤","🤍","🤎","💖","💘","💕","💞","💓","💗","💟","❣️","💌"]

# 🔐 Tracking
processed_messages = set()
forwarded_hashes = set()
HASH_ORIGINS, HASH_SOURCE, LOGGED_DUPES = {}, {}, set()
HASH_FILE = "forwarded_hashes.txt"

# 📥 Load hash data
if os.path.exists(HASH_FILE):
    with open(HASH_FILE, "r") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) == 3:
                hval, src_id, tgt_id = parts
                forwarded_hashes.add(hval)
                HASH_SOURCE[hval] = src_id
                HASH_ORIGINS[hval] = tgt_id

def save_hash(hval, src, tgt):
    with open(HASH_FILE, "a") as f:
        f.write(f"{hval}|{src}|{tgt}\n")

def extract_media_links(msg):
    patterns = [
        r"https?://drive\.google\.com/[^\s]+",
        r"https?://photos\.app\.goo\.gl/[^\s]+"
    ]
    return [link for p in patterns for link in re.findall(p, msg.content)]

async def compute_hash(attachment: discord.Attachment) -> str:
    data = await attachment.read()
    return hashlib.sha256(data).hexdigest()

async def forward_media(msg: discord.Message):
    if msg.id in processed_messages:
        return

    links = extract_media_links(msg)
    target = bot.get_channel(TARGET_CHANNEL_ID)
    trouble = bot.get_channel(TROUBLESHOOT_CHANNEL_ID)
    if not target or not trouble: return

    valid, new_hashes = [], []
    guild_id = msg.guild.id

    for a in msg.attachments:
        if a.filename.lower().endswith(".gif"): continue
        try: hval = await compute_hash(a)
        except: continue
        if hval in forwarded_hashes:
            if hval not in LOGGED_DUPES:
                src = HASH_SOURCE.get(hval, "unknown")
                tgt = HASH_ORIGINS.get(hval, "unknown")
                await trouble.send(
                    f"⚠️ Duplicate: `{a.filename}`\n🔹 [Original](https://discord.com/channels/{guild_id}/{SOURCE_CHANNEL_ID}/{src})\n"
                    f"🔸 [Copy](https://discord.com/channels/{guild_id}/{TARGET_CHANNEL_ID}/{tgt})"
                )
                LOGGED_DUPES.add(hval)
            continue
        valid.append(a)
        new_hashes.append(hval)

    if not valid and not links: return

    try:
        content = "\n".join(links) if links else None
        files = [await a.to_file() for a in valid]
        sent = await target.send(content=content, files=files or None)
    except discord.Forbidden:
        await trouble.send("🚫 Bot lacks permission to post in target channel.")
        return
    except discord.HTTPException as e:
        await trouble.send(f"⚠️ Error while forwarding: `{e}`")
        return
    except Exception as e:
        await trouble.send(f"💥 Unexpected error: `{e}`")
        return

    for h in new_hashes:
        forwarded_hashes.add(h)
        HASH_SOURCE[h] = str(msg.id)
        HASH_ORIGINS[h] = str(sent.id)
        save_hash(h, str(msg.id), str(sent.id))

    processed_messages.add(msg.id)

async def run_cleardupe(channel, guild, trigger=None, processing=None):
    trouble = bot.get_channel(TROUBLESHOOT_CHANNEL_ID)
    found = []

    async for msg in channel.history(limit=100):
        for a in msg.attachments:
            if a.filename.lower().endswith(".gif"): continue
            try: hval = await compute_hash(a)
            except: continue
            if hval in forwarded_hashes and HASH_ORIGINS.get(hval) != str(msg.id):
                src_id = HASH_SOURCE.get(hval, "unknown")
                link = f"https://discord.com/channels/{guild.id}/{SOURCE_CHANNEL_ID}/{src_id}"
                found.append((a.filename, msg.id, link))

    if found:
        for fname, msg_id, link in found:
            await trouble.send(f"♻️ Removed dupe: `{fname}`\n🔗 [Original]({link})")
            try: await (await channel.fetch_message(msg_id)).delete()
            except: pass
    else:
        await trouble.send("✅ No duplicates found.")

    for m in (trigger, processing):
        if m:
            try: await m.delete()
            except: pass

@bot.command(name="cleardupe")
async def cleardupe_legacy(ctx):
    if ctx.channel.id != TARGET_CHANNEL_ID:
        await ctx.send("❌ Run in the target channel.")
        return
    processing = await ctx.send("🛠️ Processing...")
    await run_cleardupe(ctx.channel, ctx.guild, trigger=ctx.message, processing=processing)

@tree.command(name="cleardupe", description="Scan and remove duplicated media")
async def cleardupe_slash(interaction: discord.Interaction):
    trouble = bot.get_channel(TROUBLESHOOT_CHANNEL_ID)

    if not interaction.guild or not interaction.channel or interaction.channel.id != TARGET_CHANNEL_ID:
        await interaction.response.send_message("❌ Run this command in the target channel.", ephemeral=True)
        return

    await interaction.response.defer()
    try:
        sent = await interaction.followup.send("🛠️ Processing...")
        await run_cleardupe(interaction.channel, interaction.guild, processing=sent)
    except Exception as e:
        await trouble.send(f"💥 Error in slash command: `{e}`")
        await interaction.followup.send("⚠️ Something went wrong during processing.")

@bot.event
async def on_raw_reaction_add(payload):
    emoji = str(payload.emoji)
    if payload.channel_id != SOURCE_CHANNEL_ID: return
    if emoji not in HEART_EMOJIS and emoji != TRIGGER_EMOJI: return
    if payload.message_id in processed_messages: return

    trouble = bot.get_channel(TROUBLESHOOT_CHANNEL_ID)
    channel = bot.get_channel(payload.channel_id)
    if not channel: return
    try: msg = await channel.fetch_message(payload.message_id)
    except discord.NotFound: return

    await forward_media(msg)

    # ⭐ Starboard post immediately
    if emoji == TRIGGER_EMOJI:
        starboard = bot.get_channel(STARBOARD_CHANNEL_ID)
        if not starboard: return
        embed = discord.Embed(description=msg.content or "(no text)", color=0xFEE75C)
        embed.set_author(name=msg.author.display_name, icon_url=msg.author.display_avatar.url)
        embed.set_footer(text=f"⭐ added by <@{payload.user_id}> in #{channel.name}")
        if msg.attachments:
            embed.set_image(url=msg.attachments[0].url)
        try:
            await starboard.send(embed=embed)
        except discord.Forbidden:
            if trouble: await trouble.send("🚫 Can't post to starboard.")

@bot.event
async def on_guild_channel_pins_update(channel, _):
    if channel.id != SOURCE_CHANNEL_ID: return
    async for msg in channel.history(limit=50):
        if msg.type == discord.MessageType.pins_add:
            try: await msg.delete()
            except discord.Forbidden: pass
        elif msg.pinned:
            await forward_media(msg)

@bot.event
async def on_ready():
    cogs_to_load = [
        "cogs.birthday",
        "cogs.liza_ai",
        "cogs.message",
        "cogs.funfact",
        "cogs.verify",
        "cogs.nostalgia_pull",
        "cogs.nostalgia_media"
        "cogs.game_state"
        "cogs.story_engine"
        "cogs.utils"
        "cogs.main2.py"
    ]

    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded {cog}")
        except Exception as e:
            print(f"❌ Failed to load {cog}: {e}")

    try:
        synced = await bot.tree.sync()
        print(f"🌐 Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"⚠️ Failed to sync slash commands: {e}")

    print(f"👋 Logged in as {bot.user.name}")

# 🚀 Launch
keep_alive()
bot.run(TOKEN)

