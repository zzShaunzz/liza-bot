# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Chunk 1: Imports, Logging, Env, Key Rotation, AI Engine,
#          GameState, Lifecycle Helpers, Character Definitions,
#          bold_name & Prompt Builders
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import os
import re
import httpx
import asyncio
import logging
import discord
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands, Interaction
from collections import defaultdict
from datetime import datetime, timedelta

# ┧ Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zombie_game")

# ┧ Environment Variables
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
key_cooldowns: dict[str, datetime] = {}

# ┧ OpenRouter Key Rotation
def is_key_on_cooldown(key: str) -> bool:
    return key in key_cooldowns and datetime.utcnow() < key_cooldowns[key]

def set_key_cooldown(key: str, seconds: int = 600):
    key_cooldowns[key] = datetime.utcnow() + timedelta(seconds=seconds)

async def send_openrouter_request(payload: dict) -> dict:
    tried = set()
    for key in OPENROUTER_API_KEYS:
        if key in tried or is_key_on_cooldown(key):
            continue
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload, headers=headers, timeout=30
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            tried.add(key)
            if e.response.status_code in (401, 429):
                logger.warning(f"Key {key[:6]} cooldown ({e.response.status_code})")
                set_key_cooldown(key)
                continue
            raise
    raise RuntimeError("All OpenRouter keys exhausted.")

# ┧ AI Text Generator
async def generate_ai_text(messages: list, temperature: float = 0.8) -> str | None:
    if active_game and active_game.terminated:
        return None
    payload = {"model": MODEL, "messages": messages, "temperature": temperature}
    try:
        data = await send_openrouter_request(payload)
        content = data["choices"][0]["message"]["content"].strip()
        if content:
            logger.info(f"AI → {content}")
            return content
    except Exception as e:
        logger.error(f"AI request error: {e}")
    return None

# ┧ Game State & Lifecycle
class GameState:
    def __init__(self, initiator: int):
        self.initiator = initiator
        self.round = 0
        self.alive: list[str] = []
        self.dead: list[str] = []
        self.last_choice: str | None = None
        self.options: list[str] = []
        self.stats = {
            "helped":      defaultdict(int),
            "resourceful": defaultdict(int),
            "sinister":    defaultdict(int),
            "dignified":   defaultdict(int),
            "bonds":       defaultdict(int),
            "conflicts":   defaultdict(int)
        }
        self.story_seed: str | None = None
        self.story_context: str = ""
        self.terminated: bool = False
        self.round_number: int = 1

active_game: GameState | None = None

def end_game():
    global active_game
    if active_game:
        active_game.terminated = True

def is_active() -> bool:
    return active_game is not None and not active_game.terminated

async def generate_unique_setting() -> str:
    msgs = [
        {"role": "system", "content": "You are a horror storyteller."},
        {"role": "user", "content": "🎬 Generate a unique setting for a zombie survival story in one vivid, eerie sentence."}
    ]
    return await generate_ai_text(msgs) or "A fog-choked wasteland of half-sunken skyscrapers."

async def start_game_async(user_id: int):
    global active_game
    active_game = GameState(user_id)
    active_game.alive = list(CHARACTER_INFO.keys())
    active_game.story_seed = await generate_unique_setting()
    active_game.story_context = f"Setting: {active_game.story_seed}\n"

# ┧ Character Definitions
CHARACTER_INFO = {
    "Shaun Sadsarin":   {"age":15,"gender":"Male","traits":["empathetic","stubborn","agile","semi-reserved","improviser"],"siblings":["Addison Sadsarin"],"likely_pairs":["Addison Sadsarin","Aiden Muy","Gabe Muy","Dylan Pastorin"],"likely_conflicts":["Jordan"]},
    "Addison Sadsarin":{"age":16,"gender":"Female","traits":["kind","patient","responsible","lacks physicality","semi-obstinate"],"siblings":["Shaun Sadsarin"],"likely_pairs":["Kate Nainggolan","Jill Nainggolan","Shaun Sadsarin","Vivian Muy"],"likely_conflicts":["Dylan Pastorin"]},
    "Dylan Pastorin":  {"age":21,"gender":"Male","traits":["confident","wannabe-gunner","brash","slow","semi-manipulable","extrovert"],"siblings":[],"likely_pairs":["Noah Nainggolan","Gabe Muy","Shaun Sadsarin","Vivian Muy"],"likely_conflicts":["Kate Nainggolan"]},
    "Noah Nainggolan":  {"age":18,"gender":"Male","traits":["spontaneous","weeaboo","semi-aloof","brawler"],"siblings":["Kate Nainggolan","Jill Nainggolan"],"likely_pairs":["Gabe Muy","Jill Nainggolan","Kate Nainggolan","Dylan Pastorin"],"likely_conflicts":["Jill Nainggolan"]},
    "Jill Nainggolan":  {"age":16,"gender":"Female","traits":["conniving","demure","mellow","swimmer"],"siblings":["Kate Nainggolan","Noah Nainggolan"],"likely_pairs":["Kate Nainggolan","Noah Nainggolan","Addison Sadsarin","Gabe Muy"],"likely_conflicts":["Noah Nainggolan"]},
    "Kate Nainggolan":  {"age":14,"gender":"Female","traits":["cheeky","manipulative","bold","persuasive"],"siblings":["Jill Nainggolan","Noah Nainggolan"],"likely_pairs":["Dylan Pastorin","Gabe Muy","Addison Sadsarin","Shaun Sadsarin"],"likely_conflicts":["Aiden Muy"]},
    "Vivian Muy":       {"age":18,"gender":"Female","traits":["wise","calm","insightful","secret genius"],"siblings":["Gabe Muy","Aiden Muy","Ella Muy","Nico Muy"],"likely_pairs":["Dylan Pastorin","Ella Muy","Aiden Muy","Addison Sadsarin"],"likely_conflicts":["Gabe Muy"]},
    "Gabe Muy":         {"age":17,"gender":"Male","traits":["wrestler","peacekeeper","withdraws under pressure","light-weight"],"siblings":["Vivian Muy","Aiden Muy","Ella Muy","Nico Muy"],"likely_pairs":["Aiden Muy","Nico Muy","Shaun Sadsarin","Noah Nainggolan"],"likely_conflicts":["Addison Sadsarin"]},
    "Aiden Muy":        {"age":14,"gender":"Male","traits":["crafty","short","observant","chef"],"siblings":["Vivian Muy","Gabe Muy","Ella Muy","Nico Muy"],"likely_pairs":["Shaun Sadsarin","Jordan","Nico Muy","Addison Sadsarin"],"likely_conflicts":["Ella Muy"]},
    "Ella Muy":         {"age":11,"gender":"Female","traits":["physically reliant","luckiest"],"siblings":["Vivian Muy","Gabe Muy","Aiden Muy","Nico Muy"],"likely_pairs":["Addison Sadsarin","Jill Nainggolan","Kate Nainggolan","Vivian Muy"],"likely_conflicts":["Shaun Sadsarin"]},
    "Nico Muy":         {"age":12,"gender":"Male","traits":["daring","comical","risk-taker","needs guidance"],"siblings":["Vivian Muy","Gabe Muy","Aiden Muy","Ella Muy"],"likely_pairs":["Jordan","Aiden Muy","Gabe Muy","Shaun Sadsarin"],"likely_conflicts":["Vivian Muy"]},
    "Jordan":           {"age":13,"gender":"Male","traits":["easy-going","quietly skilled","funny"],"siblings":[],"likely_pairs":["Nico Muy","Gabe Muy","Aiden Muy","Dylan Pastorin"],"likely_conflicts":["Dylan Pastorin"]}
}
CHARACTERS = list(CHARACTER_INFO.keys())

# ┧ Bolding Helper for Prompts
def bold_name(name: str) -> str:
    return f"**{name}**"

# ┧ Prompt Builders
def build_scene_prompt() -> str:
    g = active_game
    traits = "\n".join([
        f"{bold_name(n)}: {', '.join(CHARACTER_INFO.get(n, {}).get('traits', ['Unknown']))}"
        for n in g.alive
    ])
    return (
        "You are a text-only assistant. Do not generate or suggest images under any circumstances. "
        "Entire text length should fit within a single Discord message. Do not speak as an assistant or offer commentary.\n\n"
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join([bold_name(n) for n in g.alive])}\n"
        f"💀 Dead: {', '.join([bold_name(n) for n in g.dead])}\n"
        f"🧠 Traits:\n{traits}\n\n"
        "🎬 Continue the story. Include every alive character. Format each action as a bullet using •. "
        "Keep bullets short, vivid, and on their own lines. Avoid repeating previous scenes. "
        "Never revive dead characters. Do not list choices or options."
    )

def build_scene_summary_prompt(scene_text: str) -> str:
    return (
        f"{active_game.story_context}\n"
        f"Scene:\n{scene_text}\n\n"
        "🧠 Summarize the above scene in one concise sentence."
    )

def build_health_prompt() -> str:
    g = active_game
    return (
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join(g.alive)}\n\n"
        "🧠 For each character, describe their physical condition in 2–3 words. "
        "Do not speak as an assistant. Stay in-character. Format each as a bullet using •. "
        "After character bullets, add one ambient bullet describing the atmosphere. "
        "Do not include dead characters."
    )

def build_group_dynamics_prompt() -> str:
    g = active_game
    return (
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join(g.alive)}\n\n"
        "Summarize current group dynamics in 3–5 emotionally resonant bullet points. "
        "Focus on emerging bonds and rising tensions. Avoid listing every character."
    )

def build_dilemma_prompt(scene_text: str, health_text: str) -> str:
    return (
        f"{active_game.story_context}\n"
        f"Scene:\n{scene_text}\n\n"
        f"Health:\n{health_text}\n\n"
        "🧠 Describe a new problem that arises. Do not include choices. "
        "Format exactly two bullet points using •."
    )

def build_choices_prompt(dilemma_text: str) -> str:
    return (
        f"{active_game.story_context}\n"
        f"Dilemma:\n{dilemma_text}\n\n"
        "Based on the above, list exactly 2 distinct numbered choices (1. and 2.) for the survivors. "
        "Do not continue the story or describe past actions—only present the options."
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Chunk 2: Emojis, Speed Control, Health Tiers,
#          Bolding, Bullet Formatting, Streaming & Animations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Character Emoji Mapping
CHARACTER_EMOJIS = {
    "Shaun Sadsarin":   "<:hawhar:>",
    "Addison Sadsarin": "<:feeling_silly:>",
    "Dylan Pastorin":   "<:approved:>",
    "Noah Nainggolan":  "<:sillynoah:>",
    "Jill Nainggolan":  "<:que:>",
    "Kate Nainggolan":  "<:sigma:>",
    "Vivian Muy":       "<:leshame:>",
    "Gabe Muy":         "<:zesty:>",
    "Aiden Muy":        "<:aidun:>",
    "Ella Muy":         "<:ellasigma:>",
    "Nico Muy":         "<:sips_milk:>",
    "Jordan":           "<:agua:>"
}

# Speed Control
SPEED_MULTIPLIERS = {
    "normal":  1.0,
    "fast":    0.6,
    "veryfast":0.3
}
current_speed = "normal"

def get_delay(base: float = 1.0) -> float:
    return base * SPEED_MULTIPLIERS.get(current_speed, 1.0)

# Health Tier Assignment
def assign_health_tier(index: int) -> str:
    if index == 0:
        return "🟢"
    if index == 1:
        return "🟡"
    return "🔴"

# Bolding Character Names
def bold_character_names(text: str) -> str:
    if not isinstance(text, str):
        return ""
    # remove existing markdown
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    for full in CHARACTER_INFO:
        first = full.split()[0]
        variants = [
            f"{full}'s", f"{full}’s",
            f"{first}'s", f"{first}’s",
            full, first
        ]
        for v in variants:
            text = re.sub(rf"\b{re.escape(v)}\b", f"**{v}**", text)
    return text

# Bullet Formatting & Enforcement
def format_bullet(text: str) -> str:
    return f"• {text.strip().lstrip('•-').strip()}"

def split_into_sentences(text: str) -> list[str]:
    return re.split(r'(?<=[.!?])\s+', text.strip())

def enforce_bullets(text: str) -> list[str]:
    lines = text.splitlines()
    bullets, buf = [], ""
    for line in lines:
        stripped = line.strip().lstrip("•").lstrip("*")
        if not stripped:
            continue
        is_bullet = line.strip().startswith(("•", "*"))
        has_name  = any(name.split()[0] in stripped for name in CHARACTER_INFO)
        if is_bullet or has_name:
            if buf:
                bullets.append(f"• {bold_character_names(buf.strip())}")
            buf = stripped
        else:
            buf += " " + stripped
    if buf:
        bullets.append(f"• {bold_character_names(buf.strip())}")

    final = []
    for b in bullets:
        plain = re.sub(r"\*\*(.*?)\*\*", r"\1", b)
        if not any(n.split()[0] in plain for n in CHARACTER_INFO):
            for sent in split_into_sentences(plain):
                if sent:
                    final.append(f"• {sent.strip()}")
        else:
            final.append(b)

    spaced = []
    for b in final:
        spaced.append(b)
        spaced.append("")
    return spaced

# Streaming Bullets in a Single Message
async def stream_bullets_in_message(
    channel: discord.TextChannel,
    bullets: list[str],
    delay: float = 0.8
):
    try:
        msg = await channel.send("...")
    except Exception as e:
        logger.warning(f"Stream init failed: {e}")
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

# Countdown and Animation Helpers
async def countdown_message(
    msg: discord.Message,
    seconds: int,
    prefix: str = "",
    final_text: str | None = None
):
    for i in range(seconds, 0, -1):
        if active_game and active_game.terminated:
            return
        try:
            await msg.edit(content=f"{prefix} {i}")
        except Exception:
            return
        await asyncio.sleep(1)
    if final_text:
        try:
            await msg.edit(content=final_text)
        except Exception:
            return

async def animate_game_start(
    msg: discord.Message,
    stop_event: asyncio.Event,
    base: str = "🧟‍♀️ Game is starting"
):
    dots = ["", ".", "..", "..."]
    i = 0
    while not stop_event.is_set():
        try:
            await msg.edit(content=f"{base}{dots[i % len(dots)]}")
        except Exception:
            return
        await asyncio.sleep(0.6)
        i += 1

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Chunk 3: AI Generators, Cog Class, Round Flow, Voting & Utilities
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ┧ AI-Generator Wrappers
async def generate_scene(g: GameState, deaths_list: list[str], survivors_list: list[str]) -> str | None:
    g.dead = deaths_list
    g.alive = survivors_list
    raw = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating cinematic zombie survival scenes."},
        {"role": "user",   "content": build_scene_prompt()}
    ])
    auto_track_deaths(raw or "", g)
    auto_track_stats(raw or "", g)
    auto_track_relationships(raw or "", g)
    return raw

async def generate_scene_summary(text: str, g: GameState) -> str | None:
    raw = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator summarizing a zombie survival scene."},
        {"role": "user",   "content": build_scene_summary_prompt(text)}
    ], temperature=0.7)
    auto_track_stats(raw or "", g)
    return raw

async def generate_health_report(g: GameState) -> str | None:
    raw = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating a health report."},
        {"role": "user",   "content": build_health_prompt()}
    ])
    auto_track_stats(raw or "", g)
    return raw

async def generate_group_dynamics(g: GameState) -> str | None:
    raw = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator describing group dynamics."},
        {"role": "user",   "content": build_group_dynamics_prompt()}
    ])
    auto_track_stats(raw or "", g)
    auto_track_relationships(raw or "", g)
    return raw

async def generate_dilemma(scene: str, health: str, g: GameState) -> str | None:
    raw = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating a new dilemma. Do not list choices."},
        {"role": "user",   "content": build_dilemma_prompt(scene, health)}
    ], temperature=0.9)
    auto_track_stats(raw or "", g)
    return raw

async def generate_choices(dilemma: str) -> str | None:
    return await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating exactly two numbered choices."},
        {"role": "user",   "content": build_choices_prompt(dilemma)}
    ], temperature=0.8)


# ┧ ZombieGame Cog
class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="lizazombie")
    async def lizazombie_cmd(self, ctx: commands.Context):
        if is_active():
            await ctx.send("⚠️ A zombie game is already running.")
            return
        await start_game_async(ctx.author.id)
        msg = await ctx.send("🧟‍♀️ Game is starting…")
        stop = asyncio.Event()
        task = asyncio.create_task(animate_game_start(msg, stop))
        await asyncio.sleep(get_delay(3.0))
        stop.set()
        await task
        await self.run_round(ctx.channel)

    @app_commands.command(name="lizazombie", description="Start the zombie survival game")
    async def lizazombie_slash(self, interaction: Interaction):
        if interaction.channel.id != ZOMBIE_CHANNEL_ID:
            await interaction.response.send_message("❌ Use this in the zombie channel.", ephemeral=True)
            return
        if is_active():
            await interaction.response.send_message("⚠️ A game is already running.", ephemeral=True)
            return
        await interaction.response.send_message("🧟‍♀️ Game is starting…", ephemeral=True)
        await start_game_async(interaction.user.id)
        msg = await interaction.channel.send("Countdown to undead horror:")
        await countdown_message(msg, 3, "🧟‍♀️ Starting in", "🧟‍♀️ Let’s go!")
        await self.run_round(interaction.channel)

    @commands.command(name="endzombie")
    async def endzombie_cmd(self, ctx: commands.Context):
        if not is_active():
            await ctx.send("⚠️ No active game to end.")
            return
        active_game.terminated = True
        await ctx.send("🛑 Ending the zombie game…")
        await self.end_summary(ctx.channel)
        end_game()

    @app_commands.command(name="endzombie", description="End the zombie survival game")
    async def endzombie_slash(self, interaction: Interaction):
        if not is_active():
            await interaction.response.send_message("⚠️ No active game to end.", ephemeral=True)
            return
        active_game.terminated = True
        await interaction.response.send_message("🛑 Ending the zombie game…", ephemeral=True)
        await self.end_summary(interaction.channel)
        end_game()

    async def run_round(self, channel: discord.TextChannel):
        g = active_game
        g.round += 1
        if g.terminated:
            await channel.send("🛑 Game terminated.")
            return

        # Scene
        raw_scene = await generate_scene(g, g.dead, g.alive)
        if not raw_scene:
            await channel.send("⚠️ Scene generation failed.")
            return
        scene_bullets = enforce_bullets(bold_character_names(raw_scene))
        await channel.send(f"🎭 **Scene {g.round_number}**")
        await stream_bullets_in_message(channel, scene_bullets, delay=get_delay(4.5))
        g.story_context += "\n".join(scene_bullets) + "\n"

        # Summary
        raw_summary = await generate_scene_summary("\n".join(scene_bullets), g)
        if raw_summary:
            await channel.send("📝 **Summary**")
            await channel.send(bold_character_names(raw_summary))
            g.story_context += f"Summary: {raw_summary}\n"

        # Health
        raw_health = await generate_health_report(g)
        if not raw_health:
            await channel.send("⚠️ Health report failed.")
            return
        health_bullets = enforce_bullets(bold_character_names(raw_health))
        await channel.send("🩺 **Health Status**")
        await stream_bullets_in_message(channel, health_bullets, delay=get_delay(2.0))

        # Group Dynamics
        raw_dynamics = await generate_group_dynamics(g)
        if raw_dynamics:
            dynamics_bullets = enforce_bullets(bold_character_names(raw_dynamics))
            await channel.send("💬 **Group Dynamics**")
            await stream_bullets_in_message(channel, dynamics_bullets, delay=get_delay(3.5))
            g.story_context += "\n".join(dynamics_bullets) + "\n"

        # Dilemma
        raw_dilemma = await generate_dilemma(raw_scene, raw_health, g)
        if not raw_dilemma:
            await channel.send("⚠️ Dilemma generation failed.")
            return
        dilemma_bullets = enforce_bullets(bold_character_names(raw_dilemma))
        await channel.send(f"🧠 **Dilemma – Round {g.round_number}**")
        await stream_bullets_in_message(channel, dilemma_bullets, delay=get_delay(5.0))

        # Choices
        raw_choices = await generate_choices("\n".join(dilemma_bullets))
        if not raw_choices:
            await channel.send("⚠️ Choice generation failed.")
            return
        choices = [ln.strip() for ln in raw_choices.splitlines() if ln.startswith(("1.", "2."))]
        g.options = choices[:2]
        await channel.send("🔀 **Choices**")
        await stream_bullets_in_message(channel, g.options, delay=get_delay(4.5))

        # Voting
        vote_msg = await channel.send("🗳️ React with 1️⃣ or 2️⃣ to vote")
        await vote_msg.add_reaction("1️⃣")
        await vote_msg.add_reaction("2️⃣")
        await self.wait_for_votes(vote_msg, channel)

    async def wait_for_votes(self, message: discord.Message, channel: discord.TextChannel):
        g = active_game
        deadline = datetime.utcnow() + timedelta(seconds=20)
        first_vote = None
        last_counts = {"1️⃣": 0, "2️⃣": 0}
        while datetime.utcnow() < deadline and not g.terminated:
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
        g.last_choice = g.options[0] if last_counts["1️⃣"] >= last_counts["2️⃣"] else g.options[1]
        await channel.send("🗳️ **Voting closed**")
        await self.resolve_outcome(channel)

    async def resolve_outcome(self, channel: discord.TextChannel):
        g = active_game
        prompt = (
            f"{g.story_context}\n"
            f"Chosen: {g.last_choice}\n"
            f"Alive: {', '.join(g.alive)}\n"
            "Describe consequences, including any deaths."
        )
        raw = await generate_ai_text([
            {"role": "system", "content": "Horror narrator detailing outcome."},
            {"role": "user",   "content": prompt}
        ], temperature=0.85)
        if not raw:
            await channel.send("⚠️ Outcome generation failed.")
            end_game()
            return

        await channel.send(f"🩸 **End of Round {g.round}**")
        narration = enforce_bullets(bold_character_names(raw))
        await stream_bullets_in_message(channel, narration, delay=get_delay(4.5))

        match_d = re.search(r"Deaths:\s*(.*?)\nSurvivors:", raw, re.DOTALL|re.IGNORECASE)
        deaths = enforce_bullets(match_d.group(1)) if match_d else infer_deaths_from_narration(narration)
        survivors = [b for b in enforce_bullets(raw) if b not in deaths]

        await channel.send("💀 **Deaths This Round**")
        await stream_bullets_in_message(channel, deaths, delay=get_delay(1.2))
        await channel.send("🧍 **Survivors**")
        await stream_bullets_in_message(channel, survivors, delay=get_delay(1.2))

        for line in deaths:
            name = re.sub(r"^\W+|\W+$","", line)
            if name in g.alive:
                g.alive.remove(name); g.dead.append(name)

        if len(g.alive) <= 1:
            if g.alive:
                await channel.send(f"🏆 {bold_name(g.alive[0])} survives!")
            else:
                await channel.send("💀 No one survives.")
            await self.end_summary(channel)
            end_game()
        else:
            g.round_number += 1
            await self.run_round(channel)

    async def end_summary(self, channel: discord.TextChannel):
        g = active_game
        await channel.send("📜 **Game Summary**")
        deaths = [f"• {bold_name(n)}" for n in reversed(g.dead)] or ["• None"]
        await stream_bullets_in_message(channel, deaths, delay=get_delay(4.5))

        stats_lines = []
        for key, emoji, label in [
            ("helped","🏅","Most helpful"),
            ("resourceful","🔧","Most resourceful"),
            ("sinister","😈","Most sinister"),
            ("dignified","🕊️","Most dignified")
        ]:
            top = get_top_stat(g.stats.get(key, {}))
            if top != "None":
                stats_lines.append(f"{emoji} **{label}:**\n• {bold_name(top)}")

        bonds = sorted(g.stats["bonds"].items(), key=lambda x: x[1], reverse=True)
        if bonds:
            p1, p2 = bonds[0][0]
            stats_lines.append(f"🤝 **Greatest bond:**\n• {bold_name(p1)} & {bold_name(p2)}")
        conflicts = sorted(g.stats["conflicts"].items(), key=lambda x: x[1], reverse=True)
        if conflicts:
            p1, p2 = conflicts[0][0]
            stats_lines.append(f"⚔️ **Biggest conflict:**\n• {bold_name(p1)} vs {bold_name(p2)}")

        await channel.send("📊 **Final Stats**")
        await stream_bullets_in_message(channel, stats_lines, delay=get_delay(4.5))


# ┧ Cog Setup
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    await bot.tree.sync()
    logger.info("✅ ZombieGame cog loaded and slash commands synced")


# ┧ Utility Functions
def auto_track_deaths(raw_scene: str, g: GameState):
    for bullet in raw_scene.split("•")[1:]:
        txt = bullet.strip().lower()
        for name in g.alive[:]:
            if re.search(rf"\b{name.lower()}\b", txt) and re.search(r"(vanish|dragged|bitten|crushed|devoured)", txt):
                g.alive.remove(name); g.dead.append(name)

def infer_deaths_from_narration(bullets: list[str]) -> list[str]:
    deaths = set()
    for line in bullets:
        for name in CHARACTER_INFO:
            if name in line and re.search(r"(die|dead|fall|drag|bitten)", line, re.IGNORECASE):
                deaths.add(name)
    return [f"• {d}" for d in deaths]

def auto_track_stats(text: str, g: GameState):
    patterns = {
        "helped":      r"(help|assist|protect|save)",
        "resourceful": r"(improvise|solve|navigate|strategize)",
        "sinister":    r"(betray|attack|abandon|sabotage)",
        "dignified":   r"(grace|sacrifice|honor|calm)"
    }
    for name in CHARACTER_INFO:
        for key, pat in patterns.items():
            if re.search(rf"{re.escape(name)}.*{pat}", text or "", re.IGNORECASE):
                g.stats[key][name] += 1

def auto_track_relationships(text: str, g: GameState):
    for n1 in g.alive:
        for n2 in g.alive:
            if n1 == n2: continue
            if re.search(rf"{re.escape(n1)}.*(share|trust).*{re.escape(n2)}", text or "", re.IGNORECASE):
                g.stats["bonds"][(n1,n2)] += 1
            if re.search(rf"{re.escape(n1)}.*(fight|argue).*{re.escape(n2)}", text or "", re.IGNORECASE):
                g.stats["conflicts"][(n1,n2)] += 1

def get_top_stat(stat_dict: dict) -> str:
    return max(stat_dict.items(), key=lambda x: x[1])[0] if stat_dict else "None"

async def tally_votes(message: discord.Message) -> dict[str,int]:
    counts = {"1️⃣":0, "2️⃣":0}
    for reaction in message.reactions:
        if reaction.emoji in counts:
            async for user in reaction.users():
                if not user.bot:
                    counts[reaction.emoji] += 1
    return counts

