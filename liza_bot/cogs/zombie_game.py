import os
import re
import httpx
import asyncio
import logging
import aiohttp
import discord
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from collections import defaultdict

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
OPENROUTER_API_KEYS = [key for key in OPENROUTER_API_KEYS if key]  # Filter out None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧠 OpenRouter Request with Key Rotation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def send_openrouter_request(payload):
    for key in OPENROUTER_API_KEYS:
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
            if e.response.status_code in [401, 429]:
                logger.warning(f"Key failed with status {e.response.status_code}, trying next...")
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
    
# ---------- Formatting ----------
def bold_name(name: str) -> str:
    return f"**{name}**"

def bold_character_names(text: str) -> str:
    for name in CHARACTER_INFO:
        # Bold possessives first (e.g. "Kate's")
        text = re.sub(
            rf"(?<!\*)\b({re.escape(name)})'s\b(?!\*)",
            r"**\1**'s",
            text
        )

        # Bold full name (e.g. "Kate Nainggolan")
        text = re.sub(
            rf"(?<!\*)\b({re.escape(name)})\b(?!\*)",
            r"**\1**",
            text
        )

        # Bold first name only if not already bolded
        first_name = name.split()[0]
        text = re.sub(
            rf"(?<!\*)\b({re.escape(first_name)})\b(?!\*)",
            r"**\1**",
            text
        )

    return text

def format_bullet(text: str) -> str:
    """Ensure clean bullet formatting without double bullets."""
    return f"• {text.strip().lstrip('•').strip()}"

def split_into_sentences(text: str) -> list:
    """Split ambient narration into individual sentences."""
    return re.split(r'(?<=[.!?])\s+', text.strip())

def enforce_bullets(text: str) -> list:
    """Clean and consolidate bullet content into full lines with spacing."""
    lines = text.splitlines()
    bullets = []
    current = ""

    for line in lines:
        stripped = line.strip().lstrip("•").lstrip("*")
        if not stripped:
            continue

        contains_name = any(name.split()[0] in stripped for name in CHARACTER_INFO)
        is_bullet = line.strip().startswith("•") or line.strip().startswith("*")

        # Start a new bullet if line is a bullet or contains a character name
        if is_bullet or contains_name:
            if current:
                cleaned = current.strip().rstrip("*")
                bullets.append(f"• {bold_character_names(cleaned)}")
            current = stripped
        else:
            current += " " + stripped

    # Flush final bullet
    if current:
        cleaned = current.strip().rstrip("*")
        bullets.append(f"• {bold_character_names(cleaned)}")

    # Split ambient narration bullets into individual sentences
    final_bullets = []
    for b in bullets:
        if any(name.split()[0] in b for name in CHARACTER_INFO):
            final_bullets.append(b)
        else:
            for sentence in split_into_sentences(b):
                if sentence.strip():
                    final_bullets.append(f"• {sentence.strip()}")

    # Add spacing between bullets
    spaced = []
    for b in final_bullets:
        spaced.append(b)
        spaced.append("")  # blank line for pacing

    return spaced
    
async def stream_bullets_in_message(
    channel: discord.TextChannel,
    bullets: list,
    delay: float = 0.8
):
    """Send one message and edit it to reveal bullets progressively."""
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

async def countdown_message(message: discord.Message, seconds: int, prefix: str = ""):
    for i in range(seconds, 0, -1):
        if active_game and active_game.terminated:
            return
        try:
            await message.edit(content=f"{prefix} {i}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Countdown failed: {e}")
            break
    try:
        await message.edit(content="✅ Voting has ended!")
    except Exception as e:
        logger.warning(f"Final edit failed: {e}")

# ---------- Characters ----------
CHARACTER_INFO = {
    "Shaun Sadsarin": {
        "age": 15, "gender": "Male",
        "traits": ["quick planner", "boxing experience", "fast", "heat-sensitive", "pattern-adapter"],
        "siblings": ["Addison Sadsarin"],
        "likely_pairs": ["Addison Sadsarin", "Aiden Muy", "Gabe Muy", "Dylan Pastorin"],
        "likely_conflicts": ["Jordan"]
    },
    "Addison Sadsarin": {
        "age": 16, "gender": "Female",
        "traits": ["kind", "patient", "versatile", "physically weak", "slow decision-maker"],
        "siblings": ["Shaun Sadsarin"],
        "likely_pairs": ["Shaun Sadsarin", "Jill Nainggolan", "Kate Nainggolan", "Vivian Muy"],
        "likely_conflicts": ["Dylan Pastorin"]
    },
    "Dylan Pastorin": {
        "age": 21, "gender": "Male",
        "traits": ["mentally brave", "protective", "smart with firearms", "slow mover", "manipulation-prone", "extroverted"],
        "siblings": [],
        "likely_pairs": ["Noah Nainggolan", "Gabe Muy", "Shaun Sadsarin", "Vivian Muy"],
        "likely_conflicts": ["Kate Nainggolan"]
    },
    "Noah Nainggolan": {
        "age": 18, "gender": "Male",
        "traits": ["physically capable", "fighter", "not a planner"],
        "siblings": ["Kate Nainggolan", "Jill Nainggolan"],
        "likely_pairs": ["Gabe Muy", "Jill Nainggolan", "Kate Nainggolan", "Dylan Pastorin"],
        "likely_conflicts": ["Jill Nainggolan"]
    },
    "Jill Nainggolan": {
        "age": 16, "gender": "Female",
        "traits": ["conniving", "lucky", "swimmer"],
        "siblings": ["Kate Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Kate Nainggolan", "Noah Nainggolan", "Addison Sadsarin", "Gabe Muy"],
        "likely_conflicts": ["Noah Nainggolan"]
    },
    "Kate Nainggolan": {
        "age": 14, "gender": "Female",
        "traits": ["manipulative", "quick-witted", "enduring", "persuasive"],
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
        "traits": ["wrestler", "peacekeeper", "withdraws under pressure", "on the smaller side"],
        "siblings": ["Vivian Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Aiden Muy", "Nico Muy", "Shaun Sadsarin", "Noah Nainggolan"],
        "likely_conflicts": ["Addison Sadsarin"]
    },
    "Aiden Muy": {
        "age": 14, "gender": "Male",
        "traits": ["agile", "crafty", "chef", "mental reader"],
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
        self.story_context = ""  # NEW: accumulates narrative for continuity
        self.terminated = False
        self.round_number = 1

active_game = None

def end_game():
    global active_game
    if active_game:
        active_game.terminated = True

def is_active():
    return active_game is not None and not active_game.terminated

async def generate_ai_text(messages, temperature=0.9):
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

# ---------- Prompt Builders ----------

def build_scene_prompt():
    g = active_game

    traits = "\n".join([
        f"{bold_name(n)}: {', '.join(CHARACTER_INFO.get(n.strip(), {}).get('traits', ['Unknown']))}"
        for n in g.alive
    ])

    return (
        "You are a text-only assistant. Do not generate or suggest images under any circumstances. "
        "Do not speak as an assistant. Do not offer help, commentary, or meta-observations. Stay fully in-character and in-world."
        "The world has fallen to a zombie outbreak. The survivors are hunted, exhausted, and emotionally frayed. Every scene continues their desperate struggle against the undead and each other."
        "Respond only with narrative, dialogue, and bullet-pointed text.\n\n"
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join([bold_name(n) for n in g.alive])}\n"
        f"🧠 Traits:\n{traits}\n\n"
        "🎬 Continue the story. Include every alive character. "
        "Format each action as a bullet point using •. Keep bullets short and on their own lines."
        "Avoid repeating scenes or plotlines from previous sessions."
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
        msg = await ctx.send("🧟‍♀️ Zombie survival game starting in...")
        await countdown_message(msg, 3, "🧟‍♀️ Zombie survival game starting in...")
        await msg.edit(content="🧟‍♀️ Game loading...")
        await self.run_round(ctx.channel)

    @app_commands.command(name="lizazombie", description="Start a zombie survival game")
    async def lizazombie_slash(self, interaction: discord.Interaction):
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
        await self.run_round(interaction.channel)

    @commands.command(name="endzombie")
    async def end_zombie_game(self, ctx: commands.Context):
        if not is_active():
            await ctx.send("⚠️ No active zombie game to end.")
            return
        await ctx.send("🛑 Manually ending the zombie game...")
        active_game.terminated = True
        await self.end_summary(ctx.channel)
        end_game()

    @app_commands.command(name="endzombie", description="Manually end the zombie game")
    async def end_zombie_slash(self, interaction: discord.Interaction):
        if not is_active():
            await interaction.response.send_message("⚠️ No active zombie game to end.", ephemeral=True)
            return
        await interaction.response.send_message("🛑 Manually ending the zombie game...")
        active_game.terminated = True
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
        scene_bullets = [
        format_bullet(bold_character_names(line.lstrip("•").strip()))
        for line in enforce_bullets(scene_text)
        if line.strip()
        ]
        await channel.send(f"━━━━━━━━━━━━━━\n🎭 **Scene {g.round_number}**")
        await stream_bullets_in_message(channel, scene_bullets, delay=4.7)
        g.story_context += "\n".join(scene_bullets) + "\n"
        g.story_context = "\n".join(g.story_context.strip().splitlines()[-12:])  # keep last 12 lines

        # Phase 2: Summary
        raw_summary = await generate_scene_summary("\n".join(scene_bullets), g)
        if raw_summary:
            await channel.send("━━━━━━━━━━━━━━\n📝 **Scene Summary**")
            await channel.send(bold_character_names(raw_summary.strip()))
            g.story_context += f"Summary: {raw_summary.strip()}\n"

        # Phase 3: Health
        raw_health = await generate_health_report(g)
        if not raw_health:
            await channel.send("⚠️ Health report failed.")
            return
        
        raw_bolded = bold_character_names(raw_health)
        enforced = enforce_bullets(raw_bolded)
        
        cleaned_health_lines = []
        for line in enforced:
            if ":" in line:
                name, status = line.split(":", 1)
                # Keep only the first sentence or phrase before ambient narration
                status_clean = status.strip().split(".")[0].split("The ")[0].strip()
                cleaned_line = f"{name.strip()}: {status_clean}"
                cleaned_health_lines.append(cleaned_line)
        
        # Track which characters were mentioned
        reported = set()
        for line in enforced:
            for name in CHARACTER_INFO:
                if name in line:
                    reported.add(name)
        
        # Add missing characters with fallback status
        for name in CHARACTER_INFO:
            if name not in reported:
                enforced.append(bold_character_names(f"{name}: *No status reported*"))
        
        # Final formatting: Health Status
        raw_health = await generate_health_report(g)
        if not raw_health:
            await channel.send("⚠️ Health report failed.")
            return
        
        raw_bolded_health = bold_character_names(raw_health)
        enforced_health = enforce_bullets(raw_bolded_health)

        # Clean up health lines to remove scene spillover
        cleaned_health_lines = []
        for line in enforced_health:
            if ":" in line:
                name, status = line.split(":", 1)
                cleaned_line = f"{name.strip()}: {status.strip().split('.')[0]}"
                cleaned_health_lines.append(cleaned_line)
        
        # Track which characters were mentioned
        reported = set()
        for line in enforced_health:
            for name in CHARACTER_INFO:
                if name in line:
                    reported.add(name)
        
        # Add missing characters with fallback status
        for name in CHARACTER_INFO:
            if name not in reported:
                enforced_health.append(bold_character_names(f"{name}: *No status reported*"))
        
        # Clean and format
        health_bullets = [
            format_bullet(bold_character_names(line))
            for line in cleaned_health_lines
            if line.strip() and line.strip() != "•"
        ]
        
        await channel.send("━━━━━━━━━━━━━━\n🩺 **Health Status**\n")
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
        
            await channel.send("━━━━━━━━━━━━━━\n💬 **Group Dynamics**")
            await stream_bullets_in_message(channel, dynamics_bullets, delay=3.5)

        # Phase 4: Dilemma
        raw_dilemma = await generate_dilemma(raw_scene, raw_health, g)
        if raw_dilemma:
            # Filter out choice-related lines
            filtered_lines = [
                line for line in raw_dilemma.splitlines()
                if not line.strip().startswith(("A.", "B.", "C.", "D.", "E.", "F.", "What do you do?"))
            ]
        
            dilemma_bullets = [
                format_bullet(bold_character_names(line.lstrip("•").strip()))
                for line in filtered_lines
                if line.strip() and line.strip() != "•"
            ]
        
            await channel.send(f"━━━━━━━━━━━━━━\n🧠 **Dilemma – Round {g.round_number}**")
            await stream_bullets_in_message(channel, dilemma_bullets, delay=5.0)

        # Phase 5: Choices
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
        await channel.send("━━━━━━━━━━━━━━\n🔀 **Choices**")
        await stream_bullets_in_message(channel, g.options, delay=4.5)

        # Voting
        choices_msg = await channel.send("🗳️ React to vote!")
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

        # Phase 6: Outcome
        outcome_prompt = (
            f"{g.story_context}\n"
            f"The group chose: {g.last_choice}\n"
            f"Alive characters: {', '.join(g.alive)}\n"
            "🧠 Describe how this choice changes the situation. "
            "Be vivid but concise. Then clearly list deaths and survivors in bullet format under headings 'Deaths:' and 'Survivors:'."
        )
        raw_outcome = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator describing consequences of group decisions."},
            {"role": "user", "content": outcome_prompt}
        ], temperature=0.85)

        if not raw_outcome:
            await channel.send("⚠️ Outcome generation failed.")
            end_game()
            return

        # Parse deaths/survivors from AI text
        deaths_match = re.search(r"Deaths:\s*(.*?)\n\s*Survivors:", raw_outcome, re.DOTALL | re.IGNORECASE)
        survivors_match = re.search(r"Survivors:\s*(.*)", raw_outcome, re.DOTALL | re.IGNORECASE)
        
        deaths_list = enforce_bullets(deaths_match.group(1)) if deaths_match else []
        survivors_list = enforce_bullets(survivors_match.group(1)) if survivors_match else []
        
        # ✅ Fix 5: Ensure one survivor
        if len(deaths_list) >= len(CHARACTER_INFO):
            all_names = list(CHARACTER_INFO)
            still_alive = [name for name in all_names if name not in deaths_list]
            if not still_alive:
                survivor = random.choice(all_names)
                deaths_list = [name for name in deaths_list if name != survivor]
                survivors_list.append(survivor)

        # Update game state
        g.dead.extend([re.sub(r"^\W+", "", b).strip("*• ").strip() for b in deaths_list if b])
        g.alive = [re.sub(r"^\W+", "", b).strip("*• ").strip() for b in survivors_list if b]

        # Send outcome narration
        bulleted_narration = []
        
        await channel.send("━━━━━━━━━━━━━━\n📘 **Outcome**")
        
        if not bulleted_narration:
            await channel.send("⚠️ No outcome narration was generated.")
        else:
            for bullet in bulleted_narration:
                await channel.send(bullet)
                await asyncio.sleep(4.0)
        
        # Split narration into clean bullet lines
        sentences = re.split(r'(?<=[.!?])\s+', narration_only)
        bulleted_narration = [
            format_bullet(bold_character_names(s.strip().lstrip("•")))
            for s in sentences
            if s.strip() and s.strip() != "•"
        ]
        
        # Stream bullets in a single edited message
        outcome_msg = await channel.send("‎")  # invisible placeholder
        full_text = ""
        for line in bulleted_narration:
            full_text += line + "\n"
            await outcome_msg.edit(content=full_text.strip())
            await asyncio.sleep(0.5)
        
        # Update story context
        g.story_context += narration_only + "\n"

        # Send deaths and survivors
        await channel.send("━━━━━━━━━━━━━━\n💀 **Deaths This Round**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, deaths_list, delay=1.2)
        await channel.send("━━━━━━━━━━━━━━\n🧍 **Remaining Survivors**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, survivors_list, delay=1.2)

        # End condition check
        if len(g.alive) <= 1:
            if len(g.alive) == 1:
                await channel.send(f"🏆 {bold_name(g.alive[0])} is the sole survivor!")
            else:
                await channel.send("💀 No survivors remain.")
            await self.end_summary(channel)
            end_game()
            return

        # Continue to next round
        g.round_number += 1
        await self.run_round(channel)

    async def end_summary(self, channel: discord.TextChannel):
        g = active_game
        await channel.send("━━━━━━━━━━━━━━\n📜 **Game Summary**")

        valid_deaths = [name for name in g.dead if name and name.lower() != "none"]
        deaths_block = [f"• {bold_name(name)}" for name in valid_deaths]
        
        if not deaths_block:
            deaths_block = ["• None"]
        await channel.send("🪦 **Deaths (most recent first)**")
        await stream_bullets_in_message(channel, deaths_block, delay=4.5)

        # Compute top stats safely
        def safe_top(stat_dict):
            return get_top_stat(stat_dict) if stat_dict else "None"
        
        most_helpful = safe_top(g.stats.get("helpful", {}))
        most_sinister = safe_top(g.stats.get("sinister", {}))
        most_resourceful = safe_top(g.stats.get("resourceful", {}))
        most_dignified = safe_top(g.stats.get("dignified", {}))
        
        bonds = sorted(g.stats.get("bonds", {}).items(), key=lambda x: x[1], reverse=True)
        conflicts = sorted(g.stats.get("conflicts", {}).items(), key=lambda x: x[1], reverse=True)
        bond_pair = bonds[0][0] if bonds else ("None", "None")
        conflict_pair = conflicts[0][0] if conflicts else ("None", "None")
        
        # Build final stats bullets
        final_stats = [
            f"🏅 Most helpful:\n• {bold_name(most_helpful)}",
            f"😈 Most sinister:\n• {bold_name(most_sinister)}",
            f"🔧 Most resourceful:\n• {bold_name(most_resourceful)}",
            f"🤝 Greatest bond:\n• {bold_name(bond_pair[0])} & {bold_name(bond_pair[1])}",
            f"⚔️ Biggest opps:\n• {bold_name(conflict_pair[0])} vs {bold_name(conflict_pair[1])}",
            f"🕊️ Most dignified:\n• {bold_name(most_dignified)}"
        ]
        
        # Filter out any "None" entries
        final_stats = [line for line in final_stats if "None" not in line]
        
        # Stream final stats in one message
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
        raw_summary = await generate_scene_summary(scene_text)
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
def auto_track_stats(text: str, g):
    if not text:
        return  # Skip if text is None or empty

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

