import os
import re
import httpx
import asyncio
import logging
import aiohttp
import discord
from dotenv import load_dotenv
from discord.ext import commands
from discord import Interaction
from discord import app_commands
from collections import defaultdict
from datetime import datetime, timedelta
import random

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔧 Logging Setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zombie_game")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌱 Environment Variables
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
load_dotenv()

ZOMBIE_CHANNEL_ID = int(os.getenv("ZOMBIE_CHANNEL_ID", "0"))
MODEL = os.getenv("MODEL")

OPENROUTER_API_KEYS = [
    os.getenv("OPENROUTER_API_KEY_1"),
    os.getenv("OPENROUTER_API_KEY_2"),
    os.getenv("OPENROUTER_API_KEY_3"),
    os.getenv("OPENROUTER_API_KEY_4"),
    os.getenv("OPENROUTER_API_KEY_5"),
    os.getenv("OPENROUTER_API_KEY_6"),
]
OPENROUTER_API_KEYS = [key for key in OPENROUTER_API_KEYS if key]
key_cooldowns = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔁 OpenRouter Key Rotation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def is_key_on_cooldown(key):
    return key in key_cooldowns and datetime.utcnow() < key_cooldowns[key]

def set_key_cooldown(key, seconds=600):
    key_cooldowns[key] = datetime.utcnow() + timedelta(seconds=seconds)

async def send_openrouter_request(payload):
    tried_keys = set()

    for key in OPENROUTER_API_KEYS:
        if key in tried_keys:
            continue
        if is_key_on_cooldown(key):
            logger.info(f"⏳ Skipping key on cooldown: {key[:6]}...")
            continue

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            tried_keys.add(key)
            if e.response.status_code in [401, 429]:
                logger.warning(f"Key failed with status {e.response.status_code}, trying next...")
                set_key_cooldown(key, seconds=600)
                continue
            raise

    raise RuntimeError("All OpenRouter keys exhausted or invalid.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧠 AI Text Generator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def generate_ai_text(messages, temperature=0.8):
    if active_game and active_game.terminated:
        return None

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature
    }

    try:
        response = await send_openrouter_request(payload)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if content:
            logger.info(f"AI returned:\n{content}")
            return content
        logger.warning("AI response was empty.")
    except Exception as e:
        logger.error(f"AI request error: {type(e).__name__} - {e}")

    logger.error("AI request failed after key rotation.")
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧍 Character Definitions (up to Ella Muy)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHARACTER_INFO = {
    "Shaun Sadsarin": {
        "age": 15, "gender": "Male",
        "traits": ["empathetic", "stubborn", "agile", "semi-reserved", "improviser"],
        "siblings": ["Addison Sadsarin"],
        "likely_pairs": ["Addison Sadsarin", "Aiden Muy", "Gabe Muy", "Dylan Pastorin"],
        "likely_conflicts": ["Jordan"]
    },
    "Addison Sadsarin": {
        "age": 16, "gender": "Female",
        "traits": ["kind", "patient", "responsible", "lacks physicality", "semi-obstinate"],
        "siblings": ["Shaun Sadsarin"],
        "likely_pairs": ["Kate Nainggolan", "Jill Nainggolan", "Shaun Sadsarin", "Vivian Muy"],
        "likely_conflicts": ["Dylan Pastorin"]
    },
    "Dylan Pastorin": {
        "age": 21, "gender": "Male",
        "traits": ["confident", "wannabe-gunner", "brash", "slow", "semi-manipulable", "extrovert"],
        "siblings": [],
        "likely_pairs": ["Noah Nainggolan", "Gabe Muy", "Shaun Sadsarin", "Vivian Muy"],
        "likely_conflicts": ["Kate Nainggolan"]
    },
    "Noah Nainggolan": {
        "age": 18, "gender": "Male",
        "traits": ["spontaneous", "weeaboo", "semi-aloof", "brawler"],
        "siblings": ["Kate Nainggolan", "Jill Nainggolan"],
        "likely_pairs": ["Gabe Muy", "Jill Nainggolan", "Kate Nainggolan", "Dylan Pastorin"],
        "likely_conflicts": ["Jill Nainggolan"]
    },
    "Jill Nainggolan": {
        "age": 16, "gender": "Female",
        "traits": ["conniving", "demure", "mellow", "swimmer"],
        "siblings": ["Kate Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Kate Nainggolan", "Noah Nainggolan", "Addison Sadsarin", "Gabe Muy"],
        "likely_conflicts": ["Noah Nainggolan"]
    },
    "Kate Nainggolan": {
        "age": 14, "gender": "Female",
        "traits": ["cheeky", "manipulative", "bold", "persuasive"],
        "siblings": ["Jill Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Dylan Pastorin", "Gabe Muy", "Addison Sadsarin", "Shaun Sadsarin"],
        "likely_conflicts": ["Aiden Muy"]
    },
    "Vivian Muy": {
        "age": 18, "gender": "Female",
        "traits": ["wise", "calm", "insightful", "secret genius"],
        "siblings": ["Gabe Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Dylan Pastorin", "Ella Muy", "Aiden Muy", "Addison Sadsarin"],
        "likely_conflicts": ["Gabe Muy"]
    },
    "Gabe Muy": {
        "age": 17, "gender": "Male",
        "traits": ["wrestler", "peacekeeper", "withdraws under pressure", "light-weight"],
        "siblings": ["Vivian Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Aiden Muy", "Nico Muy", "Shaun Sadsarin", "Noah Nainggolan"],
        "likely_conflicts": ["Addison Sadsarin"]
    },
    "Aiden Muy": {
        "age": 14, "gender": "Male",
        "traits": ["crafty", "short", "observant", "chef"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Shaun Sadsarin", "Jordan", "Nico Muy", "Addison Sadsarin"],
        "likely_conflicts": ["Ella Muy"]
    },
    "Ella Muy": {
        "age": 11, "gender": "Female",
        "traits": ["physically reliant", "luckiest"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Nico Muy"],
        "likely_pairs": ["Addison Sadsarin", "Jill Nainggolan", "Kate Nainggolan", "Vivian Muy"],
        "likely_conflicts": ["Shaun Sadsarin"]
    },
        "Nico Muy": {
        "age": 12, "gender": "Male",
        "traits": ["daring", "comical", "risk-taker", "needs guidance"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Ella Muy"],
        "likely_pairs": ["Jordan", "Aiden Muy", "Gabe Muy", "Shaun Sadsarin"],
        "likely_conflicts": ["Vivian Muy"]
    },
    "Jordan": {
        "age": 13, "gender": "Male",
        "traits": ["easy-going", "quietly skilled", "funny"],
        "siblings": [],
        "likely_pairs": ["Nico Muy", "Gabe Muy", "Aiden Muy", "Dylan Pastorin"],
        "likely_conflicts": ["Dylan Pastorin"]
    }
}
CHARACTERS = list(CHARACTER_INFO.keys())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧠 Game State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class GameState:
    def __init__(self, initiator: int):
        self.initiator = initiator
        self.round = 0
        self.alive = CHARACTERS.copy()
        self.dead = []
        self.last_choice = None
        self.last_events = ""
        self.options = []
        self.votes = {}
        self.stats = {
            "helped": defaultdict(int),
            "resourceful": defaultdict(int),
            "sinister": defaultdict(int),
            "dignified": defaultdict(int),
            "bonds": defaultdict(int),
            "conflicts": defaultdict(int)
        }
        self.story_seed = None
        self.story_context = ""
        self.terminated = False
        self.round_number = 1

active_game = None

def end_game():
    global active_game
    if active_game:
        active_game.terminated = True

def is_active():
    return active_game is not None and not active_game.terminated

async def generate_unique_setting():
    messages = [
        {"role": "system", "content": "You are a horror storyteller."},
        {"role": "user", "content": "🎬 Generate a unique setting for a zombie survival story. Be vivid, eerie, and specific. Avoid generic locations. Describe the environment in one sentence."}
    ]
    return await generate_ai_text(messages)

async def start_game_async(user_id: int):
    global active_game
    active_game = GameState(user_id)
    active_game.story_seed = await generate_unique_setting()
    active_game.story_context = f"Setting: {active_game.story_seed}\n"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⏱️ Speed Control
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SPEED_MULTIPLIERS = {
    "normal": 1.0,
    "fast": 0.6,
    "veryfast": 0.3
}
current_speed = "normal"

def get_delay(base: float = 1.0) -> float:
    return base * SPEED_MULTIPLIERS.get(current_speed, 1.0)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🩺 Health Tier Assignment
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def assign_health_tier(index: int) -> str:
    if index == 0:
        return "🟢"
    elif index == 1:
        return "🟡"
    else:
        return "🔴"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧍 Character Emoji Mapping
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHARACTER_EMOJIS = {
    "Shaun Sadsarin": "<:hawhar:>",
    "Addison Sadsarin": "<:feeling_silly:>",
    "Dylan Pastorin": "<:approved:>",
    "Noah Nainggolan": "<:sillynoah:>",
    "Jill Nainggolan": "<:que:>",
    "Kate Nainggolan": "<:sigma:>",
    "Vivian Muy": "<:leshame:>",
    "Gabe Muy": "<:zesty:>",
    "Aiden Muy": "<:aidun:>",
    "Ella Muy": "<:ellasigma:>",
    "Nico Muy": "<:sips_milk:>",
    "Jordan": "<:agua:>"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔠 Bolding Logic (with possessives)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def bold_name(name: str) -> str:
    return f"**{name}**"

def bold_character_names(text: str) -> str:
    if not isinstance(text, str):
        return ""

    # Strip existing bolding
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)

    for full_name in CHARACTER_INFO:
        first_name = full_name.split()[0]

        # Possessive forms — straight and curly apostrophes
        possessives = [
            f"{full_name}'s", f"{full_name}’s",
            f"{first_name}'s", f"{first_name}’s"
        ]
        for variant in possessives:
            text = re.sub(rf"\b{re.escape(variant)}\b", f"**{variant}**", text)

        # Non-possessive full name
        text = re.sub(rf"\b{re.escape(full_name)}\b", f"**{full_name}**", text)

        # Non-possessive first name
        text = re.sub(rf"\b{re.escape(first_name)}\b", f"**{first_name}**", text)

    return text

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# • Bullet Formatting
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def format_bullet(text: str) -> str:
    return f"• {text.strip().lstrip('•-').strip()}"

def split_into_sentences(text: str) -> list:
    return re.split(r'(?<=[.!?])\s+', text.strip())

def enforce_bullets(text: str) -> list:
    lines = text.splitlines()
    bullets = []
    current = ""

    for line in lines:
        stripped = line.strip().lstrip("•").lstrip("*")
        if not stripped:
            continue

        contains_name = any(name.split()[0] in stripped for name in CHARACTER_INFO)
        is_bullet = line.strip().startswith("•") or line.strip().startswith("*")

        if is_bullet or contains_name:
            if current:
                cleaned = current.strip().rstrip("*")
                bullets.append(f"• {bold_character_names(cleaned)}")
            current = stripped
        else:
            current += " " + stripped

    if current:
        cleaned = current.strip().rstrip("*")
        bullets.append(f"• {bold_character_names(cleaned)}")

    final_bullets = []
    for b in bullets:
        if any(name.split()[0] in b for name in CHARACTER_INFO):
            final_bullets.append(b)
        else:
            for sentence in split_into_sentences(b):
                if sentence.strip():
                    final_bullets.append(f"• {sentence.strip()}")

    spaced = []
    for b in final_bullets:
        spaced.append(b)
        spaced.append("")
    return spaced

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 💬 Bullet Streaming
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def stream_bullets_in_message(
    channel: discord.TextChannel,
    bullets: list,
    delay: float = 0.8
):
    try:
        msg = await channel.send("...")
    except Exception as e:
        logger.warning(f"Initial message failed: {e}")
        return

    content = ""
    for bullet in bullets:
        cleaned = bullet.strip()
        if not cleaned or cleaned == "•":
            continue

        if not cleaned.endswith(('.', '!', '?', '"', '…', '...')):
            cleaned += "."

        content += f"{cleaned}\n\n"

        try:
            await msg.edit(content=content.strip())
        except Exception as e:
            logger.warning(f"Edit failed during bullet stream: {cleaned} — {e}")
            return

        await asyncio.sleep(delay)

class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="lizazombie")
    async def lizazombie_legacy(self, ctx: commands.Context):
        if is_active():
            await ctx.send("⚠️ A zombie game is already running.")
            return

        await start_game_async(ctx.author.id)
        msg = await ctx.send("🧟 Game starting")
        stop_event = asyncio.Event()
        animation_task = asyncio.create_task(animate_game_start(msg, stop_event))
        await asyncio.sleep(get_delay(3.0))
        stop_event.set()
        await animation_task
        await self.run_round(ctx.channel)

    @app_commands.command(name="lizazombie", description="Start a zombie survival game")
    async def lizazombie_slash(self, interaction: Interaction):
        await interaction.response.send_message("🧟 Starting zombie survival game...", ephemeral=True)

        if interaction.channel.id != ZOMBIE_CHANNEL_ID:
            await interaction.followup.send("❌ Run this command in the zombie channel.", ephemeral=True)
            return

        if is_active():
            await interaction.followup.send("⚠️ A zombie game is already running.", ephemeral=True)
            return

        await start_game_async(interaction.user.id)
        msg = await interaction.channel.send("🧟 Game starting")
        stop_event = asyncio.Event()
        animation_task = asyncio.create_task(animate_game_start(msg, stop_event))
        await asyncio.sleep(get_delay(3.0))
        stop_event.set()
        await animation_task
        await self.run_round(interaction.channel)

    @commands.command(name="endzombie")
    async def end_zombie_game(self, ctx: commands.Context):
        if not is_active():
            await ctx.send("⚠️ No active zombie game to end.")
            return
        await ctx.send("🛑 Ending the zombie game...")
        active_game.terminated = True
        await self.end_summary(ctx.channel)
        end_game()

    @app_commands.command(name="endzombie", description="Manually end the zombie game")
    async def end_zombie_slash(self, interaction: Interaction):
        if not is_active():
            await interaction.response.send_message("⚠️ No active zombie game to end.", ephemeral=True)
            return
        await interaction.response.send_message("🛑 Ending the zombie game...")
        active_game.terminated = True
        await self.end_summary(interaction.channel)
        end_game()

    @commands.command(name="dead")
    async def dead_legacy(self, ctx: commands.Context):
        if not is_active():
            await ctx.send("⚠️ No active game.")
            return
        if not active_game.dead:
            await ctx.send("💀 No deaths yet.")
            return
        lines = [f"• {bold_name(name)}: {active_game.death_reasons.get(name, 'Unknown cause')}" for name in active_game.dead]
        await ctx.send("💀 **Dead Characters**")
        await stream_bullets_in_message(ctx.channel, lines, delay=1.0)

    @app_commands.command(name="dead", description="List all dead characters and how they died")
    async def dead_slash(self, interaction: Interaction):
        if not is_active():
            await interaction.response.send_message("⚠️ No active game.", ephemeral=True)
            return
        if not active_game.dead:
            await interaction.response.send_message("💀 No deaths yet.", ephemeral=True)
            return
        lines = [f"• {bold_name(name)}: {active_game.death_reasons.get(name, 'Unknown cause')}" for name in active_game.dead]
        await interaction.response.send_message("💀 **Dead Characters**")
        await stream_bullets_in_message(interaction.channel, lines, delay=1.0)

    @commands.command(name="speed")
    async def speed_legacy(self, ctx: commands.Context, mode: str = "normal"):
        global current_speed
        mode = mode.lower()
        if mode not in SPEED_MULTIPLIERS:
            await ctx.send("❌ Invalid speed. Choose: `normal`, `fast`, or `veryfast`.")
            return
        current_speed = mode
        if is_active():
            active_game.speed = mode
        await ctx.send(f"⏱️ Speed set to **{mode}**")

    @speed_legacy.error
    async def speed_legacy_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ You need to specify a speed mode: `normal`, `fast`, or `veryfast`.")

    @app_commands.command(name="speed", description="Change pacing of the game")
    @app_commands.describe(mode="Choose pacing: normal, fast, veryfast")
    async def speed_slash(self, interaction: Interaction, mode: str):
        global current_speed
        mode = mode.lower()
        if mode not in SPEED_MULTIPLIERS:
            await interaction.response.send_message("❌ Invalid speed. Choose: normal, fast, veryfast", ephemeral=True)
            return
        current_speed = mode
        if is_active():
            active_game.speed = mode
        await interaction.response.send_message(f"⏱️ Speed set to **{mode}**", ephemeral=True)

    async def run_round(self, channel: discord.TextChannel):
        g = active_game
        g.round += 1
        if g.terminated:
            await channel.send("🛑 Game has been terminated.")
            return

        # Phase 1: Scene
        raw_scene = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator generating cinematic zombie survival scenes."},
            {"role": "user", "content": build_scene_prompt()}
        ])
        if not raw_scene:
            await channel.send("⚠️ Scene generation failed.")
            return

        scene_text = bold_character_names(raw_scene)
        scene_bullets = enforce_bullets(scene_text)
        await channel.send(f"━━━━━━━━━━━━━━\n🎭 **Scene {g.round_number}**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, scene_bullets, delay=get_delay(4.5))
        g.story_context += "\n".join(scene_bullets) + "\n"
        auto_track_stats(raw_scene, g)
        auto_track_relationships(raw_scene, g)

        # Phase 2: Summary
        raw_summary = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator summarizing a zombie survival scene."},
            {"role": "user", "content": build_scene_summary_prompt("\n".join(scene_bullets))}
        ])
        if raw_summary:
            await channel.send("━━━━━━━━━━━━━━\n📝 **Scene Summary**\n━━━━━━━━━━━━━━")
            await channel.send(bold_character_names(raw_summary.strip()))
            g.story_context += f"Summary: {raw_summary.strip()}\n"

        # Phase 3: Health
        raw_health = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator generating a health report."},
            {"role": "user", "content": build_health_prompt()}
        ])
        if not raw_health:
            await channel.send("⚠️ Health report failed.")
            return

        health_bullets = []
        lines = enforce_bullets(bold_character_names(raw_health))
        for i, line in enumerate(lines):
            if ":" in line:
                raw_name, status = line.split(":", 1)
                name = re.sub(r"\*\*(.*?)\*\*", r"\1", raw_name.strip())
                char_emoji = CHARACTER_EMOJIS.get(name, "")
                tier = assign_health_tier(i)
                formatted = f"{char_emoji} {bold_name(name)} {tier}: {status.strip()}"
                health_bullets.append(f"• {formatted.strip()}")
            else:
                health_bullets.append(format_bullet(line.strip()))
        await channel.send("━━━━━━━━━━━━━━\n🩺 **Health Status**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, health_bullets, delay=get_delay(2.0))

        # Phase 4: Group Dynamics
        raw_dynamics = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator describing group dynamics."},
            {"role": "user", "content": build_group_dynamics_prompt()}
        ])
        if raw_dynamics:
            dynamics_bullets = enforce_bullets(bold_character_names(raw_dynamics))
            await channel.send("━━━━━━━━━━━━━━\n💬 **Group Dynamics**\n━━━━━━━━━━━━━━")
            await stream_bullets_in_message(channel, dynamics_bullets, delay=get_delay(3.5))
            auto_track_stats(raw_dynamics, g)
            auto_track_relationships(raw_dynamics, g)

        # Phase 5: Dilemma
        raw_dilemma = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator generating dilemmas for a survival game."},
            {"role": "user", "content": build_dilemma_prompt(raw_scene, raw_health)}
        ])
        if not raw_dilemma:
            await channel.send("⚠️ Dilemma generation failed.")
            return

        dilemma_bullets = enforce_bullets(bold_character_names(raw_dilemma))
        await channel.send(f"━━━━━━━━━━━━━━\n🧠 **Dilemma – Round {g.round_number}**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, dilemma_bullets, delay=get_delay(5.0))

        # Phase 6: Choices
        raw_choices = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator generating voting choices."},
            {"role": "user", "content": build_choices_prompt("\n".join(dilemma_bullets))}
        ])
        if not raw_choices:
            await channel.send("⚠️ Choice generation failed.")
            return

        choice_lines = [line.strip() for line in raw_choices.split("\n") if line.strip()]
        g.options = [line for line in choice_lines if line.startswith(("1.", "2."))][:2]
        if len(g.options) != 2:
            await channel.send("⚠️ AI did not return two valid choices. Ending game.")
            end_game()
            return

        await channel.send("━━━━━━━━━━━━━━\n🔀 **Choices**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, g.options, delay=get_delay(4.5))

        choices_msg = await channel.send("━━━━━━━━━━━━━━\n🗳️ React to vote!")
        await choices_msg.add_reaction("1️⃣")
        await choices_msg.add_reaction("2️⃣")

        # Phase 7: Voting with auto-advance
        vote_task = asyncio.create_task(self.wait_for_votes(choices_msg, channel))
        await vote_task

    async def wait_for_votes(self, message: discord.Message, channel: discord.TextChannel):
        g = active_game
        vote_window = 20
        first_vote_time = None
        last_vote_count = {"1️⃣": 0, "2️⃣": 0}

        for i in range(vote_window):
            if g.terminated:
                return
            msg = await channel.fetch_message(message.id)
            votes = await tally_votes(msg)
            total_votes = sum(votes.values())

            if total_votes > sum(last_vote_count.values()):
                if not first_vote_time:
                    first_vote_time = datetime.utcnow()
                elif (datetime.utcnow() - first_vote_time).total_seconds() >= 5:
                    break
            last_vote_count = votes
            await asyncio.sleep(get_delay(1.0))

        g.last_choice = g.options[0] if votes["1️⃣"] >= votes["2️⃣"] else g.options[1]
        await channel.send("🗳️ **Voting has finished!**")
        await self.resolve_outcome(channel)

    async def resolve_outcome(self, channel: discord.TextChannel):
        g = active_game
        prompt = (
            f"{g.story_context}\n"
            f"The group chose: {g.last_choice}\n"
            f"Alive characters: {', '.join(g.alive)}\n"
            "🧠 Describe how this choice affects the situation. Be vivid but concise. Include who may have died and how."
        )

        raw_outcome = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator describing consequences of group decisions."},
            {"role": "user", "content": prompt}
        ], temperature=0.85)

        if not raw_outcome:
            await channel.send("⚠️ Outcome generation failed.")
            end_game()
            return

        await channel.send(f"🩸━━━━━━━━━━━━━━━━━━━━━━━🩸\n**End of Round {g.round}**\n🩸━━━━━━━━━━━━━━━━━━━━━━━🩸")

        # Parse deaths and survivors
        deaths_match = re.search(r"Deaths:\s*(.*?)\n\s*Survivors:", raw_outcome, re.DOTALL | re.IGNORECASE)
        survivors_match = re.search(r"Survivors:\s*(.*)", raw_outcome, re.DOTALL | re.IGNORECASE)

        narration_lines = enforce_bullets(bold_character_names(raw_outcome))
        cleaned_narration = []
        for line in narration_lines:
            match = re.search(r"(\*\*.*?\*\*:.*?[a-z])\s+(?=[A-Z])", line)
            if match:
                split_index = match.end()
                cleaned_narration.append(line[:split_index].strip())
                cleaned_narration.append(line[split_index:].strip())
            else:
                cleaned_narration.append(line)
        narration_lines = cleaned_narration

        # Infer deaths if not explicitly listed
        if deaths_match:
            deaths_list = enforce_bullets(deaths_match.group(1))
        else:
            deaths_list = infer_deaths_from_narration(narration_lines)

        if survivors_match:
            survivors_list = enforce_bullets(survivors_match.group(1))
        else:
            survivors_list = [name for name in g.alive if name not in deaths_list]

        # Clean bullets
        deaths_list = [line.replace("• -", "•").replace("•  -", "•") for line in deaths_list]
        survivors_list = [line.replace("• -", "•").replace("•  -", "•") for line in survivors_list]

        # Update game state
        for line in deaths_list:
            name = line.replace("•", "").strip()
            if name in g.alive:
                g.alive.remove(name)

        if not survivors_list and deaths_list:
            still_alive = [name for name in CHARACTER_INFO if name not in deaths_list]
            if still_alive:
                survivor = random.choice(still_alive)
                deaths_list = [name for name in deaths_list if name != survivor]
                survivors_list.append(survivor)
                logger.warning(f"⚠️ No survivors listed — reviving {survivor} as fallback.")

        g.dead.extend([re.sub(r"^\W+", "", b).strip("*• ").strip() for b in deaths_list if b])
        g.alive = [re.sub(r"^\W+", "", b).strip("*• ").strip() for b in survivors_list if b]

        # Track death reasons
        if not hasattr(g, "death_reasons"):
            g.death_reasons = {}
        for line in narration_lines:
            for name in g.dead:
                if name in line and name not in g.death_reasons:
                    g.death_reasons[name] = re.sub(r"^\W+", "", line.replace("•", "").strip())

        # Stream narration
        await channel.send("━━━━━━━━━━━━━━\n📘 **Outcome**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, narration_lines, delay=get_delay(4.5))

        # Recap deaths and survivors
        await channel.send("━━━━━━━━━━━━━━\n💀 **Deaths This Round**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, deaths_list, delay=get_delay(1.2))
        await channel.send("━━━━━━━━━━━━━━\n🧍 **Remaining Survivors**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, survivors_list, delay=get_delay(1.2))

        # Endgame check
        if len(g.alive) <= 1:
            if len(g.alive) == 1:
                await channel.send(f"🏆 {bold_name(g.alive[0])} is the sole survivor!")
            else:
                await channel.send("💀 No survivors remain.")
            await self.end_summary(channel)
            end_game()
            return

        g.round_number += 1
        await self.run_round(channel)

    async def end_summary(self, channel: discord.TextChannel):
        g = active_game
        await channel.send("━━━━━━━━━━━━━━\n📜 **Game Summary**\n━━━━━━━━━━━━━━")

        valid_deaths = [name for name in g.dead if name and name.lower() != "none"]
        deaths_block = [f"• {bold_name(name)}" for name in valid_deaths]
        if not deaths_block:
            deaths_block = ["• None"]
        await channel.send("🪦 **Deaths (most recent first)**")
        await stream_bullets_in_message(channel, deaths_block, delay=get_delay(4.5))

        def safe_top(stat_dict):
            return get_top_stat(stat_dict) if stat_dict else "None"

        most_helpful = safe_top(g.stats.get("helped", {}))
        most_sinister = safe_top(g.stats.get("sinister", {}))
        most_resourceful = safe_top(g.stats.get("resourceful", {}))
        most_dignified = safe_top(g.stats.get("dignified", {}))

        bonds = sorted(g.stats.get("bonds", {}).items(), key=lambda x: x[1], reverse=True)
        conflicts = sorted(g.stats.get("conflicts", {}).items(), key=lambda x: x[1], reverse=True)
        bond_pair = bonds[0][0] if bonds else ("None", "None")
        conflict_pair = conflicts[0][0] if conflicts else ("None", "None")

        final_stats = [
            f"🏅 Most helpful:\n• {bold_name(most_helpful)}",
            f"😈 Most sinister:\n• {bold_name(most_sinister)}",
            f"🔧 Most resourceful:\n• {bold_name(most_resourceful)}",
            f"🤝 Greatest bond:\n• {bold_name(bond_pair[0])} & {bold_name(bond_pair[1])}",
            f"⚔️ Biggest opps:\n• {bold_name(conflict_pair[0])} vs {bold_name(conflict_pair[1])}",
            f"🕊️ Most dignified:\n• {bold_name(most_dignified)}"
        ]
        final_stats = [line for line in final_stats if "None" not in line]

        await channel.send("━━━━━━━━━━━━━━\n📊 **Final Stats**")
        await stream_bullets_in_message(channel, final_stats, delay=get_delay(4.5))

        recap_prompt = (
            f"{g.story_context}\n"
            f"Deaths: {', '.join(g.dead)}\n"
            f"Survivors: {', '.join(g.alive)}\n"
            f"Key choices made: {g.last_choice}\n"
            f"Strongest bond: {bond_pair[0]} & {bond_pair[1]}\n"
            f"Biggest conflict: {conflict_pair[0]} vs {conflict_pair[1]}\n\n"
            "🎬 Write a brief cinematic recap of the entire game in bullet points."
        )
        raw_summary = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator summarizing a zombie survival game."},
            {"role": "user", "content": recap_prompt}
        ])
        if raw_summary:
            summary_bullets = enforce_bullets(bold_character_names(raw_summary))
            await channel.send("🧠 **Scene Summary**")
            await stream_bullets_in_message(channel, summary_bullets, delay=get_delay(4.5))

        await channel.send("🎬 Thanks for surviving (or not) the zombie apocalypse. Until next time...")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ Cog Setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    print("✅ ZombieGame cog loaded")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🛠️ Utility Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def auto_track_stats(text: str, g):
    if not text:
        return
    for name in CHARACTER_INFO:
        if re.search(rf"{name}.*(help|assist|protect|save)", text, re.IGNORECASE):
            g.stats["helped"][name] += 1
        if re.search(rf"{name}.*(improvise|solve|navigate|strategize)", text, re.IGNORECASE):
            g.stats["resourceful"][name] += 1
        if re.search(rf"{name}.*(betray|attack|abandon|sabotage)", text, re.IGNORECASE):
            g.stats["sinister"][name] += 1
        if re.search(rf"{name}.*(grace|sacrifice|honor|calm)", text, re.IGNORECASE):
            g.stats["dignified"][name] += 1

def auto_track_relationships(text: str, g):
    if not text:
        return
    for name1 in g.alive:
        for name2 in g.alive:
            if name1 == name2:
                continue
            if re.search(rf"{name1}.*(share|nod|exchange|trust).+{name2}", text, re.IGNORECASE):
                g.stats["bonds"][(name1, name2)] += 1
            if re.search(rf"{name1}.*(argue|fight|oppose|resent).+{name2}", text, re.IGNORECASE):
                g.stats["conflicts"][(name1, name2)] += 1

def get_top_stat(stat_dict):
    return max(stat_dict.items(), key=lambda x: x[1])[0]

def infer_deaths_from_narration(bullets):
    deaths = []
    for line in bullets:
        for name in CHARACTER_INFO:
            if name in line and re.search(r"(fall|drag|vanish|seized|pulled|die|dead|choked|struggle is brief)", line, re.IGNORECASE):
                deaths.append(name)
    return list(set(deaths))

def merge_broken_quotes(lines):
    merged = []
    buffer = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("•") and not stripped.endswith(('"', '.', '!', '?')):
            buffer = stripped
        elif buffer:
            buffer += " " + stripped
            if stripped.endswith(('"', '.', '!', '?')):
                merged.append(buffer)
                buffer = ""
        else:
            merged.append(stripped)
    if buffer:
        merged.append(buffer)
    return merged

async def tally_votes(message):
    votes = {"1️⃣": 0, "2️⃣": 0}
    for reaction in message.reactions:
        if reaction.emoji in votes:
            users = [user async for user in reaction.users()]
            for user in users:
                if not user.bot:
                    votes[reaction.emoji] += 1
    return votes
