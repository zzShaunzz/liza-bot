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
# 🧠 OpenRouter Request with Key Rotation
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

# ---------- Characters ----------
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

# ---------- Game State ----------
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

# ---------- Formatting ----------
def bold_name(name: str) -> str:
    return f"**{name}**"

def bold_character_names(text: str) -> str:
    for name in CHARACTER_INFO:
        text = re.sub(
            rf"(?<!\*)\b({re.escape(name)})'s\b(?!\*)",
            r"**\1**'s",
            text
        )
        text = re.sub(
            rf"(?<!\*)\b({re.escape(name)})\b(?!\*)",
            r"**\1**",
            text
        )
        first_name = name.split()[0]
        text = re.sub(
            rf"(?<!\*)\b({re.escape(first_name)})\b(?!\*)",
            r"**\1**",
            text
        )
    return text

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

async def stream_bullets_in_message(
    channel: discord.TextChannel,
    bullets: list,
    delay: float = 0.8
):
    content = ""
    try:
        msg = await channel.send("...")
    except Exception as e:
        logger.warning(f"Initial message failed: {e}")
        return

    for bullet in bullets:
        if bullet.strip():
            content += bullet + "\n\n"
            try:
                await msg.edit(content=content.strip())
                await asyncio.sleep(delay)
            except Exception as e:
                logger.warning(f"Bullet stream failed: {e}")
                break

async def game_countdown_message(channel: discord.TextChannel, seconds: int, prefix: str = "", final_message: str = None):
    try:
        msg = await channel.send(f"{prefix} {seconds}")
        for i in range(seconds - 1, 0, -1):
            if active_game and active_game.terminated:
                return
            await asyncio.sleep(1)
            await msg.edit(content=f"{prefix} {i}")
        await asyncio.sleep(1)
        if final_message:
            await msg.edit(content=final_message)
    except Exception as e:
        logger.warning(f"Game countdown failed: {e}")

async def animate_game_start(message: discord.Message, stop_event: asyncio.Event, base_text: str = "🧟‍♀️ Game is starting"):
    dots = ["", ".", "..", "..."]
    i = 0
    while not stop_event.is_set():
        try:
            await message.edit(content=f"{base_text}{dots[i % len(dots)]}")
            await asyncio.sleep(0.6)
            i += 1
        except Exception as e:
            logger.warning(f"Game start animation failed: {e}")
            break

async def countdown_message(message: discord.Message, seconds: int, prefix: str = "", final_text: str = None):
    for i in range(seconds, 0, -1):
        if active_game and active_game.terminated:
            return
        try:
            await message.edit(content=f"{prefix} {i}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Countdown failed: {e}")
            break
    if final_text:
        try:
            await message.edit(content=final_text)
        except Exception as e:
            logger.warning(f"Final edit failed: {e}")

# ---------- Prompt Builders ----------
def build_scene_prompt():
    g = active_game
    traits = "\n".join([
        f"{bold_name(n)}: {', '.join(CHARACTER_INFO.get(n.strip(), {}).get('traits', ['Unknown']))}"
        for n in g.alive
    ])
    return (
        "You are a text-only assistant. Do not generate or suggest images under any circumstances. "
        "Entire text length should be able to fit within a Discord message (under 2,000 characters)."
        "Do not speak as an assistant. Do not offer help, commentary, or meta-observations. Stay fully in-character and in-world."
        "The world has fallen to a zombie outbreak. The survivors are hunted, exhausted, and emotionally frayed. Every scene continues their desperate struggle against the undead and each other."
        "Respond only with narrative, dialogue, and bullet-pointed text.\n\n"
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join([bold_name(n) for n in g.alive])}\n"
        f"🧠 Traits:\n{traits}\n\n"
        "🎬 Continue the story. Include every alive character. "
        "Format each action as a bullet point using •. Keep bullets short and on their own lines."
        "Avoid repeating scenes or plotlines from previous sessions."
        "Never revive characters who have died."
        "Don't treat dead characters as alive."
        "Do not list multiple options. Do not use numbered choices. Only continue the story."
    )

def build_scene_summary_prompt(scene_text):
    return (
        f"{active_game.story_context}\n"
        f"Scene:\n{scene_text}\n\n"
        "🧠 Summarize the key events in exactly one sentence."
    )

def build_health_prompt():
    g = active_game
    return (
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join(g.alive)}\n\n"
        "🧠 For each character, describe their physical condition in 2–3 words. "
        "Do not speak as an assistant. Do not offer help, commentary, or meta-observations. Stay fully in-character and in-world."
        "Format each as a bullet point using •."
        "After the bullets, describe the ambient atmosphere in a brief sentence. Do not merge character traits with narration."
        "Do not include dead characters."
        "Do not revive dead characters."
    )

def build_group_dynamics_prompt():
    g = active_game
    return (
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join(g.alive)}\n\n"
        "Summarize the current group dynamics in 3–5 bullet points. Focus only on notable relationship shifts: emerging bonds and rising tensions. Avoid listing every character. Do not repeat previous dynamics unless they’ve evolved. Keep each bullet short and emotionally resonant."
    )

def build_dilemma_prompt(scene_text, health_text):
    return (
        f"{active_game.story_context}\n"
        f"Scene:\n{scene_text}\n\n"
        f"Health:\n{health_text}\n\n"
        "🧠 Describe a new problem that arises, specific to this situation. "
        "Do not include any choices or options. Only describe the situation."
        "Format as exactly two bullet points using •."
    )

def build_choices_prompt(dilemma_text):
    return (
        f"{active_game.story_context}\n"
        f"Dilemma:\n{dilemma_text}\n\n"
        "Based on the current scene, list exactly 2 distinct choices the survivors could make next. Format each as a bullet point. Do not continue the story or describe what characters already did. These are branching options for the players to choose from."
        "Format each as a numbered bullet starting with '1.' and '2.'."
    )

# ---------- AI Generators ----------
async def generate_scene(g):
    raw_scene = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating cinematic zombie survival scenes."},
        {"role": "user", "content": build_scene_prompt()}
    ])
    auto_track_stats(raw_scene, g)
    auto_track_relationships(raw_scene, g)
    return raw_scene

async def generate_outcome(scene_text, choice_text, g):
    prompt = (
        "You are a horror narrator summarizing the consequences of a specific player choice "
        "in a zombie survival scene. Focus on what happened *because* of the choice. "
        "Return short, vivid bullet points only. Do not describe images or include voting options.\n\n"
        f"Scene:\n{scene_text}\n\n"
        f"Chosen Action:\n{choice_text}"
    )
    raw_outcome = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating outcome consequences."},
        {"role": "user", "content": prompt}
    ], temperature=0.8)
    auto_track_stats(raw_outcome, g)
    auto_track_relationships(raw_outcome, g)
    return raw_outcome

async def generate_scene_summary(scene_text, g):
    raw_summary = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator summarizing a zombie survival scene."},
        {"role": "user", "content": build_scene_summary_prompt(scene_text)}
    ], temperature=0.7)
    auto_track_stats(raw_summary, g)
    return raw_summary

async def generate_health_report(g):
    raw_health = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating a health report."},
        {"role": "user", "content": build_health_prompt()}
    ])
    auto_track_stats(raw_health, g)
    return raw_health

async def generate_group_dynamics(g):
    raw_dynamics = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator describing group dynamics."},
        {"role": "user", "content": build_group_dynamics_prompt()}
    ])
    auto_track_stats(raw_dynamics, g)
    auto_track_relationships(raw_dynamics, g)
    return raw_dynamics

async def generate_dilemma(scene_text, health_text, g):
    raw_dilemma = await generate_ai_text([
        {"role": "system", "content": (
            "You are a horror narrator generating dilemmas for a survival game. "
            "Do not generate or describe any images. Do not include voting choices. "
            "Only output text in bullet-point format."
        )},
        {"role": "user", "content": build_dilemma_prompt(scene_text, health_text)}
    ], temperature=0.9)
    auto_track_stats(raw_dilemma, g)
    return raw_dilemma

async def generate_choices(dilemma_text):
    raw_choices = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating voting choices. Only output text."},
        {"role": "user", "content": build_choices_prompt(dilemma_text)}
    ], temperature=0.8)
    return raw_choices

class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="lizazombie")
    async def lizazombie_legacy(self, ctx: commands.Context):
        await ctx.send("✅ Command registered. Preparing zombie survival game...")

        if is_active():
            await ctx.send("⚠️ A zombie game is already running.")
            return

        await start_game_async(ctx.author.id)

        msg = await ctx.send("🧟‍♀️ Game is starting")
        stop_event = asyncio.Event()
        animation_task = asyncio.create_task(animate_game_start(msg, stop_event))

        try:
            await self.run_round(ctx.channel)
        except Exception as e:
            logger.error(f"run_round crashed: {e}")
            await ctx.send("⚠️ Game failed to start.")
        finally:
            stop_event.set()
            await animation_task

    @app_commands.command(name="lizazombie", description="Start a zombie survival game")
    async def lizazombie_slash(self, interaction: Interaction):
        await interaction.response.send_message("✅ Command registered. Preparing zombie survival game...", ephemeral=True)

        if interaction.channel.id != ZOMBIE_CHANNEL_ID:
            await interaction.followup.send("❌ Run this command in the zombie channel.", ephemeral=True)
            return

        if is_active():
            await interaction.followup.send("⚠️ A zombie game is already running.", ephemeral=True)
            return

        await start_game_async(interaction.user.id)

        msg = await interaction.channel.send("🧟‍♀️ Zombie survival game starting in...")
        await countdown_message(msg, 3, "🧟‍♀️ Zombie survival game starting in...")
        await msg.edit(content="🧟‍♀️ Game loading...")

        logger.info("✅ Countdown finished. Starting run_round...")
        await self.run_round(interaction.channel)

    @commands.command(name="endzombie")
    async def end_zombie_game(self, ctx: commands.Context):
        if not is_active():
            await ctx.send("⚠️ No active zombie game to end.")
            return
        await ctx.send("🛑 Manually ending the zombie game...")
        active_game.terminated = True

        g = active_game
        await self.end_summary(ctx.channel)
        end_game()

    @app_commands.command(name="endzombie", description="Manually end the zombie game")
    async def end_zombie_slash(self, interaction: Interaction):
        if not is_active():
            await interaction.response.send_message("⚠️ No active zombie game to end.", ephemeral=True)
            return
        await interaction.response.send_message("🛑 Manually ending the zombie game...")
        active_game.terminated = True

        g = active_game
        await self.end_summary(interaction.channel)
        end_game()

    async def run_round(self, channel: discord.TextChannel):
        g = active_game
        g.round += 1

        if g.terminated:
            await channel.send("🛑 Game has been terminated.")
            return

        # Phase 1: Scene
        raw_scene = await generate_scene(g)
        if not raw_scene:
            await channel.send("⚠️ Scene generation failed.")
            return
        scene_text = bold_character_names(raw_scene)

        # Merge multi-line quotes
        merged_lines = []
        quote_buffer = ""

        for line in scene_text.splitlines():
            stripped = line.strip()
            if stripped.startswith('"') or quote_buffer:
                quote_buffer += (" " if quote_buffer else "") + stripped
                if stripped.endswith('"') or stripped.endswith(('.', '!', '?')):
                    merged_lines.append(quote_buffer.strip())
                    quote_buffer = ""
                continue
            merged_lines.append(stripped)

        scene_text = " ".join(merged_lines)

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', scene_text)

        # Format bullets
        scene_bullets = [
            format_bullet(bold_character_names(s.strip().lstrip("•")))
            for s in sentences
            if s.strip() and s.strip() != "•"
        ]

        # Fuse quote bullets with speaker actions
        fused_bullets = []
        quote_buffer = ""
        
        for line in scene_bullets:
            stripped = line.strip()
        
            # Start or continue a quote
            if stripped.startswith('"') or quote_buffer:
                quote_buffer += (" " if quote_buffer else "") + stripped
        
                # If quote ends, hold it until next speaker action
                if stripped.endswith('"') or stripped.endswith(('.', '!', '?')):
                    continue
                else:
                    continue
        
            # If we have a quote waiting, fuse it into this line
            if quote_buffer:
                fused_bullets.append(f"{stripped} {quote_buffer}".strip())
                quote_buffer = ""
            else:
                fused_bullets.append(stripped)
        
        scene_bullets = fused_bullets

        # Stream scene bullets
        await channel.send(f"━━━━━━━━━━━━━━\n🎭 **Scene {g.round_number}**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, scene_bullets, delay=4.7)

        # Update story context
        g.story_context += "\n".join(scene_bullets) + "\n"
        g.story_context = "\n".join(g.story_context.strip().splitlines()[-12:])  # keep last 12 lines

        # Phase 2: Summary
        raw_summary = await generate_scene_summary("\n".join(scene_bullets), g)

        if not raw_summary:
            await channel.send("⚠️ No summary was generated.")
            return

        await channel.send("━━━━━━━━━━━━━━\n📝 **Scene Summary**\n━━━━━━━━━━━━━━")
        await channel.send(bold_character_names(raw_summary.strip()))
        g.story_context += f"Summary: {raw_summary.strip()}\n"

        # Phase 3: Health
        raw_health = await generate_health_report(g)
        if not raw_health:
            await channel.send("⚠️ Health report failed.")
            return

        raw_bolded_health = bold_character_names(raw_health)
        enforced_health = enforce_bullets(raw_bolded_health)

        cleaned_health_lines = []
        buffer = ""

        for line in enforced_health:
            stripped = line.strip()

            if stripped.endswith(":"):
                buffer = stripped
                continue
            elif buffer:
                cleaned_health_lines.append(f"{buffer} {stripped}")
                buffer = ""
                continue
            elif ":" in stripped:
                name, status = stripped.split(":", 1)
                status_parts = re.split(r'(?<=[a-z])\s+(?=[A-Z])', status.strip(), maxsplit=1)
                descriptor = status_parts[0].strip()
                cleaned_line = f"{name.strip()}: {descriptor}"
                cleaned_health_lines.append(cleaned_line)

                if len(status_parts) > 1:
                    ambient = status_parts[1].strip()
                    cleaned_health_lines.append(ambient)
            else:
                cleaned_health_lines.append(stripped)

        reported = set()
        for line in enforced_health:
            for name in CHARACTER_INFO:
                if name in line:
                    reported.add(name)

        for name in CHARACTER_INFO:
            if name not in reported:
                enforced_health.append(bold_character_names(f"{name}: *No status reported*"))

        health_bullets = [
            format_bullet(bold_character_names(line.strip().lstrip("•")))
            for line in cleaned_health_lines
            if line.strip()
        ]

        await channel.send("━━━━━━━━━━━━━━\n🩺 **Health Status**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, health_bullets, delay=2.0)

        # Phase 3b: Group Dynamics
        raw_dynamics = await generate_group_dynamics(g)
        if raw_dynamics:
            raw_bolded_dynamics = bold_character_names(raw_dynamics)
            enforced_dynamics = enforce_bullets(raw_bolded_dynamics)

            dynamics_bullets = [
                format_bullet(line.lstrip("•").strip())
                for line in enforced_dynamics
                if line.strip() and line.strip() != "•"
            ]

            await channel.send("━━━━━━━━━━━━━━\n💬 **Group Dynamics**\n━━━━━━━━━━━━━━")
            await stream_bullets_in_message(channel, dynamics_bullets, delay=3.5)

        # Phase 4: Dilemma
        dilemma_bullets = []

        raw_dilemma = await generate_dilemma(raw_scene, raw_health, g)
        if not raw_dilemma:
            await channel.send("⚠️ Dilemma generation failed.")
            return

        filtered_lines = [
            line for line in raw_dilemma.splitlines()
            if not line.strip().startswith(("A.", "B.", "C.", "D.", "E.", "F.", "What do you do?"))
        ]

        dilemma_bullets = [
            format_bullet(bold_character_names(line.lstrip("•").strip()))
            for line in filtered_lines
            if line.strip() and line.strip() != "•"
        ]

        await channel.send(f"━━━━━━━━━━━━━━\n🧠 **Dilemma – Round {g.round_number}**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, dilemma_bullets, delay=5.0)

        raw_choices = await generate_choices("\n".join(dilemma_bullets))
        if not raw_choices:
            await channel.send("⚠️ Choice generation failed.")
            return

        choice_lines = [line.strip() for line in raw_choices.split("\n") if line.strip()]
        numbered = [line for line in choice_lines if line.startswith(("1.", "2."))]
        g.options = numbered if len(numbered) == 2 else choice_lines[:2]

        if len(g.options) != 2 or any(not opt for opt in g.options):
            await channel.send("⚠️ AI did not return two valid choices. Ending game.")
            end_game()
            return

        await channel.send("━━━━━━━━━━━━━━\n🔀 **Choices**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, g.options, delay=4.5)

        choices_msg = await channel.send("━━━━━━━━━━━━━━\n🗳️ React to vote!")
        await choices_msg.add_reaction("1️⃣")
        await choices_msg.add_reaction("2️⃣")
        countdown_msg = await channel.send("⏳ Voting ends in...")
        await countdown_message(countdown_msg, 20, "⏳ Voting ends in...")
        choices_msg = await channel.fetch_message(choices_msg.id)
        votes = await tally_votes(choices_msg)

        if votes["1️⃣"] == 0 and votes["2️⃣"] == 0:
            await channel.send("No votes cast. Game over.")
            end_game()
            return

        g.last_choice = g.options[0] if votes["1️⃣"] >= votes["2️⃣"] else g.options[1]

        outcome_prompt = (
            f"{g.story_context}\n"
            f"The group chose: {g.last_choice}\n"
            f"Alive characters: {', '.join(g.alive)}\n"
            "🧠 Describe how this choice affects the situation. "
            "Be vivid but concise. Include who may have died and how."
        )

        raw_outcome = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator describing consequences of group decisions."},
            {"role": "user", "content": outcome_prompt}
        ], temperature=0.85)

        if not raw_outcome:
            await channel.send("⚠️ Outcome generation failed.")
            end_game()
            return

        def clean_and_space_bullets(text: str) -> str:
            lines = text.split("\n")
            cleaned = []
            skip = False
            for line in lines:
                line = line.replace("• -", "•").strip()
                if line.lower().startswith("• deaths:") or line.lower().startswith("• survivors:"):
                    skip = True
                    continue
                if skip and line.startswith("•"):
                    continue
                if skip and not line.startswith("•"):
                    skip = False
                if not skip and line:
                    cleaned.append("") if line.startswith("•") else None
                    cleaned.append(line)
            return "\n".join(cleaned)

        outcome_text = clean_and_space_bullets(raw_outcome)

        await channel.send(f"🩸━━━━━━━━━━━━━━━━━━━━━━━🩸\n**End of Round {g.round}**\n🩸━━━━━━━━━━━━━━━━━━━━━━━🩸")

        deaths_match = re.search(r"Deaths:\s*(.*?)\n\s*Survivors:", raw_outcome, re.DOTALL | re.IGNORECASE)
        survivors_match = re.search(r"Survivors:\s*(.*)", raw_outcome, re.DOTALL | re.IGNORECASE)

        sentences = re.split(r'(?<=[.!?])\s+', raw_outcome)
        bulleted_narration = [
            format_bullet(bold_character_names(s.strip().lstrip("•")))
            for s in sentences
            if s.strip() and s.strip() != "•"
        ]

        cleaned_narration = []
        for line in bulleted_narration:
            match = re.search(r"(\*\*.*?\*\*:.*?)(?=\s+[A-Z])", line)
            if match:
                split_index = match.end()
                cleaned_narration.append(line[:split_index].strip())
                cleaned_narration.append(line[split_index:].strip())
            else:
                cleaned_narration.append(line)

        bulleted_narration = cleaned_narration

        if deaths_match:
            deaths_list = enforce_bullets(deaths_match.group(1))
        else:
            logger.warning("⚠️ No 'Deaths:' block found — inferring deaths from narration.")
            deaths_list = infer_deaths_from_narration(bulleted_narration)

        if survivors_match:
            survivors_list = enforce_bullets(survivors_match.group(1))
        else:
            survivors_list = [name for name in g.alive if name not in deaths_list]

        deaths_list = [line.replace("• -", "•").replace("•  -", "•") for line in deaths_list]
        survivors_list = [line.replace("• -", "•").replace("•  -", "•") for line in survivors_list]

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

        sentences = re.split(r'(?<=[.!?])\s+', raw_outcome)
        bulleted_narration = [
            format_bullet(bold_character_names(s.strip().lstrip("•")))
            for s in sentences
            if s.strip() and s.strip() != "•"
        ]

        cleaned_narration = []
        for line in bulleted_narration:
            match = re.search(r"(\*\*.*?\*\*:.*?[a-z])\s+(?=[A-Z])", line)
            if match:
                split_index = match.end()
                cleaned_narration.append(line[:split_index].strip())
                cleaned_narration.append(line[split_index:].strip())
            else:
                cleaned_narration.append(line)

        bulleted_narration = cleaned_narration

        if not bulleted_narration:
            await channel.send("⚠️ No outcome narration was generated.")
            return

        outcome_msg = await channel.send("‎")
        full_text = "━━━━━━━━━━━━━━\n📘 **Outcome**\n━━━━━━━━━━━━━━\n\n"
        chunk_limit = 1900

        for line in bulleted_narration:
            next_line = line + "\n\n"
            if len(full_text) + len(next_line) > chunk_limit:
                await outcome_msg.edit(content=full_text.strip())
                await asyncio.sleep(4.5)
                full_text = next_line
            else:
                full_text += next_line

        if full_text.strip():
            await outcome_msg.edit(content=full_text.strip())

        narration_only = raw_scene
        g.story_context += narration_only + "\n"

        await channel.send("━━━━━━━━━━━━━━\n💀 **Deaths This Round**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, deaths_list, delay=1.2)
        await channel.send("━━━━━━━━━━━━━━\n🧍 **Remaining Survivors**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, survivors_list, delay=1.2)

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
        await stream_bullets_in_message(channel, deaths_block, delay=4.5)

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
        await stream_bullets_in_message(channel, final_stats, delay=4.5)

        recap_prompt = (
            f"{g.story_context}\n"
            f"Deaths: {', '.join(g.dead)}\n"
            f"Survivors: {', '.join(g.alive)}\n"
            f"Key choices made: {g.last_choice}\n"
            f"Strongest bond: {bond_pair[0]} & {bond_pair[1]}\n"
            f"Biggest conflict: {conflict_pair[0]} vs {conflict_pair[1]}\n\n"
            "🎬 Write a brief cinematic recap of the entire game in bullet points."
        )
        raw_summary = await generate_scene_summary(recap_prompt, g)
        summary_bullets = [
            format_bullet(bold_character_names(line.lstrip("•").strip()))
            for line in raw_summary.splitlines()
            if line.strip() and line.strip() != "•"
        ]

        await channel.send("🧠 **Scene Summary**")
        await stream_bullets_in_message(channel, summary_bullets, delay=4.5)
        await channel.send("🎬 Thanks for surviving (or not) the zombie apocalypse. Until next time...")

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    print("✅ ZombieGame cog loaded")

# Utilities
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

async def tally_votes(message):
    votes = {"1️⃣": 0, "2️⃣": 0}
    for reaction in message.reactions:
        if reaction.emoji in votes:
            users = [user async for user in reaction.users()]
            for user in users:
                if not user.bot:
                    votes[reaction.emoji] += 1
    return votes
