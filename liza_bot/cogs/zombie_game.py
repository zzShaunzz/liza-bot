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
OPENROUTER_API_KEYS = [k for k in OPENROUTER_API_KEYS if k]
key_cooldowns = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔁 OpenRouter Key Rotation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def is_key_on_cooldown(key):
    return key in key_cooldowns and datetime.utcnow() < key_cooldowns[key]

def set_key_cooldown(key, seconds=600):
    key_cooldowns[key] = datetime.utcnow() + timedelta(seconds=seconds)

async def send_openrouter_request(payload):
    tried = set()
    for key in OPENROUTER_API_KEYS:
        if key in tried or is_key_on_cooldown(key):
            continue
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            tried.add(key)
            if e.response.status_code in (401, 429):
                logger.warning(f"Key failed {e.response.status_code}, cooling down.")
                set_key_cooldown(key)
                continue
            raise
    raise RuntimeError("All OpenRouter keys exhausted.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧠 AI Text Generator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def generate_ai_text(messages, temperature=0.8):
    if active_game and active_game.terminated:
        return None
    payload = {"model": MODEL, "messages": messages, "temperature": temperature}
    try:
        data = await send_openrouter_request(payload)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if content:
            logger.info(f"AI → {content}")
            return content
        logger.warning("Empty AI response.")
    except Exception as e:
        logger.error(f"AI request error: {e}")
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧟‍♂️ Startup Animation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def animate_game_start(message: discord.Message, stop_event: asyncio.Event):
    frames = ["🧟", "🧟‍♂️", "🧟‍♀️", "🧟", "🧟‍♂️", "🧟‍♀️"]
    i = 0
    while not stop_event.is_set():
        try:
            await message.edit(content=frames[i % len(frames)])
        except Exception as e:
            logger.warning(f"Animation failed: {e}")
            break
        i += 1
        await asyncio.sleep(0.5)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧍 Character Definitions
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
        self.death_reasons = {}
        self.last_choice = None
        self.options = []
        self.stats = {
            "helped": defaultdict(int),
            "resourceful": defaultdict(int),
            "sinister": defaultdict(int),
            "dignified": defaultdict(int),
            "bonds": defaultdict(int),
            "conflicts": defaultdict(int)
        }
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧩 Prompt Builders
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_scene_prompt() -> str:
    g = active_game
    return (
        f"{g.story_context}\n"
        f"Alive characters: {', '.join(g.alive)}\n"
        "🎬 Generate a cinematic zombie survival scene in bullet points."
    )

def build_scene_summary_prompt(scene_text: str) -> str:
    return (
        f"{scene_text}\n"
        "📝 Summarize the above scene in one concise paragraph."
    )

def build_health_prompt() -> str:
    g = active_game
    return (
        f"{g.story_context}\n"
        "🩺 Provide a brief health status report for each character."
    )

def build_group_dynamics_prompt() -> str:
    g = active_game
    return (
        f"{g.story_context}\n"
        "💬 Describe the current group dynamics among the survivors."
    )

def build_dilemma_prompt(raw_scene: str, raw_health: str) -> str:
    return (
        f"{raw_scene}\n\n{raw_health}\n"
        "🧠 Present a dilemma based on the above. Provide two options labeled 1. and 2."
    )

def build_choices_prompt(dilemma_text: str) -> str:
    return (
        f"{dilemma_text}\n"
        "🔀 Provide two numbered choices (1. and 2.) for the group to vote on."
    )

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
    # Remove any existing **…**
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    for full_name in CHARACTER_INFO:
        first_name = full_name.split()[0]
        possessives = [
            f"{full_name}'s", f"{full_name}’s",
            f"{first_name}'s", f"{first_name}’s"
        ]
        for variant in possessives:
            text = re.sub(
                rf"\b{re.escape(variant)}\b",
                f"**{variant}**",
                text
            )
        # Bold full name and first name
        text = re.sub(rf"\b{re.escape(full_name)}\b", f"**{full_name}**", text)
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
    bullets, current = [], ""
    for line in lines:
        stripped = line.strip().lstrip("•").lstrip("*")
        if not stripped:
            continue
        is_bullet = line.strip().startswith(("•", "*"))
        name_hit = any(name.split()[0] in stripped for name in CHARACTER_INFO)
        if is_bullet or name_hit:
            if current:
                bullets.append(f"• {bold_character_names(current.strip())}")
            current = stripped
        else:
            current += " " + stripped
    if current:
        bullets.append(f"• {bold_character_names(current.strip())}")
    # Split long bullets into sentences if no character name present
    final = []
    for b in bullets:
        has_name = any(name.split()[0] in b for name in CHARACTER_INFO)
        if not has_name:
            for sent in split_into_sentences(b):
                if sent:
                    final.append(f"• {sent.strip()}")
        else:
            final.append(b)
    # Insert blank line after each bullet for streaming
    spaced = []
    for b in final:
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
        line = bullet.strip()
        if not line or line == "•":
            continue
        if not line.endswith(('.', '!', '?', '"', '…', '...')):
            line += "."
        content += f"{line}\n\n"
        try:
            await msg.edit(content=content.strip())
        except Exception as e:
            logger.warning(f"Stream edit failed: {e}")
            return
        await asyncio.sleep(delay)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧟‍♂️ ZombieGame Commands
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="lizazombie")
    async def lizazombie_legacy(self, ctx: commands.Context):
        """Legacy start command."""
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
        """Slash start command."""
        if interaction.channel.id != ZOMBIE_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ Run this command in the zombie channel.", ephemeral=True
            )
            return

        if is_active():
            await interaction.response.send_message(
                "⚠️ A zombie game is already running.", ephemeral=True
            )
            return

        await interaction.response.send_message("🧟 Game starting...", ephemeral=True)
        await start_game_async(interaction.user.id)
        msg = await interaction.channel.send("🧟 Game starting")
        stop_event = asyncio.Event()
        animation_task = asyncio.create_task(animate_game_start(msg, stop_event))
        await asyncio.sleep(get_delay(3.0))
        stop_event.set()
        await animation_task
        await self.run_round(interaction.channel)

    @commands.command(name="endzombie")
    async def endzombie_legacy(self, ctx: commands.Context):
        """Legacy end command."""
        if not is_active():
            await ctx.send("⚠️ No active zombie game to end.")
            return

        active_game.terminated = True
        await ctx.send("🛑 Ending the zombie game...")
        await self.end_summary(ctx.channel)
        end_game()

    @app_commands.command(name="endzombie", description="Manually end the zombie game")
    async def endzombie_slash(self, interaction: Interaction):
        """Slash end command."""
        if not is_active():
            await interaction.response.send_message(
                "⚠️ No active zombie game to end.", ephemeral=True
            )
            return

        active_game.terminated = True
        await interaction.response.send_message("🛑 Ending the zombie game...", ephemeral=True)
        await self.end_summary(interaction.channel)
        end_game()

    @commands.command(name="dead")
    async def dead_legacy(self, ctx: commands.Context):
        """Legacy dead list command."""
        if not is_active():
            await ctx.send("⚠️ No active game.")
            return

        if not active_game.dead:
            await ctx.send("💀 No deaths yet.")
            return

        lines = [
            f"• {bold_name(name)}: {active_game.death_reasons.get(name, 'Unknown cause')}"
            for name in active_game.dead
        ]
        await ctx.send("💀 **Dead Characters**")
        await stream_bullets_in_message(ctx.channel, lines, delay=1.0)

    @app_commands.command(name="dead", description="List all dead characters and how they died")
    async def dead_slash(self, interaction: Interaction):
        """Slash dead list command."""
        if not is_active():
            await interaction.response.send_message("⚠️ No active game.", ephemeral=True)
            return

        if not active_game.dead:
            await interaction.response.send_message("💀 No deaths yet.", ephemeral=True)
            return

        lines = [
            f"• {bold_name(name)}: {active_game.death_reasons.get(name, 'Unknown cause')}"
            for name in active_game.dead
        ]
        await interaction.response.send_message("💀 **Dead Characters**")
        await stream_bullets_in_message(interaction.channel, lines, delay=1.0)

    @commands.command(name="speed")
    async def speed_legacy(self, ctx: commands.Context, mode: str = "normal"):
        """Legacy speed control."""
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
    async def speed_legacy_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ You need to specify a speed mode: `normal`, `fast`, or `veryfast`.")

    @app_commands.command(name="speed", description="Change pacing of the game")
    @app_commands.describe(mode="Choose pacing: normal, fast, veryfast")
    async def speed_slash(self, interaction: Interaction, mode: str):
        """Slash speed control."""
        global current_speed
        mode = mode.lower()
        if mode not in SPEED_MULTIPLIERS:
            await interaction.response.send_message(
                "❌ Invalid speed. Choose: normal, fast, veryfast", ephemeral=True
            )
            return

        current_speed = mode
        if is_active():
            active_game.speed = mode
        await interaction.response.send_message(f"⏱️ Speed set to **{mode}**", ephemeral=True)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🔄 Round Execution
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
        for i, line in enumerate(enforce_bullets(bold_character_names(raw_health))):
            if ":" in line:
                name_part, status = line.split(":", 1)
                name = re.sub(r"\*\*(.*?)\*\*", r"\1", name_part.strip())
                tier = assign_health_tier(i)
                emoji = CHARACTER_EMOJIS.get(name, "")
                health_bullets.append(f"• {emoji} {bold_name(name)} {tier}: {status.strip()}")
            else:
                health_bullets.append(format_bullet(line))
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
            g.story_context += "\n".join(dynamics_bullets) + "\n"

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

        choice_lines = [ln.strip() for ln in raw_choices.splitlines() if ln.strip().startswith(("1.", "2."))]
        g.options = choice_lines[:2]
        if len(g.options) < 2:
            await channel.send("⚠️ AI did not return two valid choices. Ending game.")
            end_game()
            return

        await channel.send("━━━━━━━━━━━━━━\n🔀 **Choices**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, g.options, delay=get_delay(4.5))

        choices_msg = await channel.send("🗳️ React with 1️⃣ or 2️⃣ to vote!")
        await choices_msg.add_reaction("1️⃣")
        await choices_msg.add_reaction("2️⃣")

        # Phase 7: Voting
        await self.wait_for_votes(choices_msg, channel)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🗳️ Vote Tally & Auto-Advance
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    async def wait_for_votes(self, message: discord.Message, channel: discord.TextChannel):
        g = active_game
        vote_deadline = datetime.utcnow() + timedelta(seconds=20)
        first_vote = None
        last_counts = {"1️⃣": 0, "2️⃣": 0}

        while datetime.utcnow() < vote_deadline and not g.terminated:
            msg = await channel.fetch_message(message.id)
            counts = await tally_votes(msg)
            total = counts["1️⃣"] + counts["2️⃣"]

            if total > sum(last_counts.values()):
                if not first_vote:
                    first_vote = datetime.utcnow()
                elif (datetime.utcnow() - first_vote).total_seconds() >= 5:
                    break
            last_counts = counts
            await asyncio.sleep(get_delay(1.0))

        # Determine winning choice
        winner = "1️⃣" if last_counts["1️⃣"] >= last_counts["2️⃣"] else "2️⃣"
        g.last_choice = g.options[0] if winner == "1️⃣" else g.options[1]
        await channel.send("🗳️ **Voting has finished!**")
        await self.resolve_outcome(channel)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⚡ Outcome Resolution & Round Recap
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
            {"role": "user",   "content": prompt}
        ], temperature=0.85)

        if not raw_outcome:
            await channel.send("⚠️ Outcome generation failed.")
            end_game()
            return

        await channel.send(f"🩸━━━━━━━━━━ End of Round {g.round} ━━━━━━━━━━🩸")

        # Parse deaths and survivors
        deaths_match = re.search(r"Deaths:\s*(.*?)\n\s*Survivors:", raw_outcome, re.DOTALL | re.IGNORECASE)
        survivors_match = re.search(r"Survivors:\s*(.*)", raw_outcome, re.DOTALL | re.IGNORECASE)

        # Break into clean bullets
        narration = enforce_bullets(bold_character_names(raw_outcome))
        cleaned = []
        for line in narration:
            # Split compound bullets if needed
            m = re.search(r"(\*\*.*?\*\*:.*?[a-z])\s+(?=[A-Z])", line)
            if m:
                idx = m.end()
                cleaned.append(line[:idx].strip())
                cleaned.append(line[idx:].strip())
            else:
                cleaned.append(line)
        
        # Determine death & survivor lists
        if deaths_match:
            deaths_list = enforce_bullets(deaths_match.group(1))
        else:
            deaths_list = infer_deaths_from_narration(cleaned)

        if survivors_match:
            survivors_list = enforce_bullets(survivors_match.group(1))
        else:
            survivors_list = [name for name in g.alive if name not in deaths_list]

        # Normalize and update game state
        deaths_list = [b.replace("•  -", "•").replace("• -", "•") for b in deaths_list]
        survivors_list = [b.replace("•  -", "•").replace("• -", "•") for b in survivors_list]

        for b in deaths_list:
            name = re.sub(r"^\W+", "", b).strip("• ").strip()
            if name in g.alive:
                g.alive.remove(name)
                g.dead.append(name)

        if not survivors_list and g.alive:
            fallback = random.choice(g.alive)
            survivors_list = [f"• {fallback}"]
            logger.warning(f"⚠️ No survivors listed—reviving {fallback} as fallback.")

        # Track death reasons
        for line in cleaned:
            for name in g.dead:
                if name in line and name not in g.death_reasons:
                    g.death_reasons[name] = re.sub(r"^\W+", "", line)

        # Stream outcome narration
        await channel.send("━━━━━━━━━━━━━━\n📘 **Outcome**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, cleaned, delay=get_delay(4.5))

        # Round recap: deaths & survivors
        await channel.send("━━━━━━━━━━━━━━\n💀 **Deaths This Round**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, deaths_list, delay=get_delay(1.2))

        await channel.send("━━━━━━━━━━━━━━\n🧍 **Remaining Survivors**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, survivors_list, delay=get_delay(1.2))

        # Endgame check
        if len(g.alive) <= 1:
            if g.alive:
                await channel.send(f"🏆 {bold_name(g.alive[0])} is the sole survivor!")
            else:
                await channel.send("💀 No survivors remain.")
            await self.end_summary(channel)
            end_game()
            return

        # Next round
        g.round_number += 1
        await self.run_round(channel)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📜 Endgame Summary & Final Stats
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    async def end_summary(self, channel: discord.TextChannel):
        g = active_game
        await channel.send("━━━━━━━━━━━━━━\n📜 **Game Summary**\n━━━━━━━━━━━━━━")

        # Deaths recap
        valid_deaths = [name for name in g.dead if name]
        deaths_block = [f"• {bold_name(name)}" for name in valid_deaths] or ["• None"]
        await channel.send("🪦 **Deaths (most recent first)**")
        await stream_bullets_in_message(channel, deaths_block, delay=get_delay(4.5))

        # Top stats
        def top_or_none(stat):
            return get_top_stat(g.stats.get(stat, {})) if g.stats.get(stat) else "None"

        most_helpful    = top_or_none("helped")
        most_resourceful = top_or_none("resourceful")
        most_sinister  = top_or_none("sinister")
        most_dignified = top_or_none("dignified")

        # Bonds & Conflicts
        sorted_bonds    = sorted(g.stats.get("bonds", {}).items(), key=lambda x: x[1], reverse=True)
        sorted_conflicts = sorted(g.stats.get("conflicts", {}).items(), key=lambda x: x[1], reverse=True)
        bond_pair       = sorted_bonds[0][0] if sorted_bonds else ("None","None")
        conflict_pair   = sorted_conflicts[0][0] if sorted_conflicts else ("None","None")

        final_stats = [
            f"🏅 Most helpful:\n• {bold_name(most_helpful)}",
            f"🔧 Most resourceful:\n• {bold_name(most_resourceful)}",
            f"😈 Most sinister:\n• {bold_name(most_sinister)}",
            f"🕊️ Most dignified:\n• {bold_name(most_dignified)}",
            f"🤝 Greatest bond:\n• {bold_name(bond_pair[0])} & {bold_name(bond_pair[1])}",
            f"⚔️ Biggest conflict:\n• {bold_name(conflict_pair[0])} vs {bold_name(conflict_pair[1])}"
        ]
        # Remove any 'None' stats
        final_stats = [stat for stat in final_stats if "None" not in stat]

        await channel.send("━━━━━━━━━━━━━━\n📊 **Final Stats**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, final_stats, delay=get_delay(4.5))

        # Cinematic recap
        recap_prompt = (
            f"{g.story_context}\n"
            f"Deaths: {', '.join(g.dead)}\n"
            f"Survivors: {', '.join(g.alive)}\n"
            f"Key choice: {g.last_choice}\n"
            f"Strongest bond: {bond_pair[0]} & {bond_pair[1]}\n"
            f"Biggest conflict: {conflict_pair[0]} vs {conflict_pair[1]}\n\n"
            "🎬 Write a brief cinematic recap of the entire game in bullet points."
        )
        raw_recap = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator summarizing a zombie survival game."},
            {"role": "user", "content": recap_prompt}
        ])
        if raw_recap:
            recap_bullets = enforce_bullets(bold_character_names(raw_recap))
            await channel.send("🎬 **Cinematic Recap**")
            await stream_bullets_in_message(channel, recap_bullets, delay=get_delay(4.5))

        await channel.send("🎬 Thanks for surviving (or not) the zombie apocalypse. Until next time...")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ Cog Setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    logger.info("✅ ZombieGame cog loaded")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🛠️ Utility Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def auto_track_stats(text: str, g: GameState):
    if not text:
        return
    patterns = {
        "helped":    r"(help|assist|protect|save)",
        "resourceful": r"(improvise|solve|navigate|strategize)",
        "sinister":  r"(betray|attack|abandon|sabotage)",
        "dignified": r"(grace|sacrifice|honor|calm)"
    }
    for name in CHARACTER_INFO:
        for stat, pat in patterns.items():
            if re.search(rf"{re.escape(name)}.*{pat}", text, re.IGNORECASE):
                g.stats[stat][name] += 1

def auto_track_relationships(text: str, g: GameState):
    if not text:
        return
    for name1 in g.alive:
        for name2 in g.alive:
            if name1 == name2:
                continue
            if re.search(rf"{re.escape(name1)}.*(share|nod|trust).*{re.escape(name2)}", text, re.IGNORECASE):
                g.stats["bonds"][(name1, name2)] += 1
            if re.search(rf"{re.escape(name1)}.*(argue|fight|oppose).*{re.escape(name2)}", text, re.IGNORECASE):
                g.stats["conflicts"][(name1, name2)] += 1

def get_top_stat(stat_dict: dict) -> str:
    return max(stat_dict.items(), key=lambda x: x[1])[0] if stat_dict else "None"

def infer_deaths_from_narration(bullets: list) -> list:
    deaths = []
    for line in bullets:
        for name in CHARACTER_INFO:
            if name in line and re.search(r"(fall|drag|die|dead|choke|seize)", line, re.IGNORECASE):
                deaths.append(name)
    return list(set(deaths))

def merge_broken_quotes(lines: list) -> list:
    merged, buffer = [], ""
    for line in lines:
        txt = line.strip()
        if txt.startswith("•") and not txt.endswith(('"', '.', '!', '?')):
            buffer = txt
        elif buffer:
            buffer += " " + txt
            if txt.endswith(('"', '.', '!', '?')):
                merged.append(buffer)
                buffer = ""
        else:
            merged.append(txt)
    if buffer:
        merged.append(buffer)
    return merged

async def tally_votes(message: discord.Message) -> dict:
    counts = {"1️⃣": 0, "2️⃣": 0}
    for reaction in message.reactions:
        if reaction.emoji in counts:
            async for user in reaction.users():
                if not user.bot:
                    counts[reaction.emoji] += 1
    return counts
