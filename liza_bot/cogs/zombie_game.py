import os
import re
import httpx
import asyncio
import logging
import aiohttp
import discord
import random
import json
from dotenv import load_dotenv
from discord.ext import commands
from discord import Interaction
from discord import app_commands
from collections import defaultdict
from datetime import datetime, timedelta

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zombie_game")

# Environment Variables
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
    os.getenv("OPENROUTER_API_KEY_7"),
]
OPENROUTER_API_KEYS = [key for key in OPENROUTER_API_KEYS if key]
key_cooldowns = {}

# Game speed settings
SPEED_SETTINGS = {
    1.0: {"scene": 4.7, "health": 2.0, "dynamics": 3.5, "dilemma": 5.0, "choices": 4.5, "summary": 4.5, "stats": 4.5},
    1.5: {"scene": 3.1, "health": 1.3, "dynamics": 2.3, "dilemma": 3.3, "choices": 3.0, "summary": 3.0, "stats": 3.0},
    2.0: {"scene": 2.4, "health": 1.0, "dynamics": 1.8, "dilemma": 2.5, "choices": 2.3, "summary": 2.3, "stats": 2.3}
}

# Global variables
active_game = None
current_speed = 1.0

# OpenRouter Request with Key Rotation
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

# AI Text Generator
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

# Characters
CHARACTER_INFO = {
    "Shaun Sadsarin": {
        "age": 15, "gender": "Male",
        "traits": ["empathetic", "stubborn", "agile", "semi-reserved", "improviser"],
        "siblings": ["Addison Sadsarin"],
        "likely_pairs": ["Addison Sadsarin", "Aiden Muy", "Gabe Muy", "Dylan Pastorin"],
        "likely_conflicts": ["Jordan"],
        "emoji": "hawhar"
    },
    "Addison Sadsarin": {
        "age": 16, "gender": "Female",
        "traits": ["kind", "patient", "responsible", "lacks physicality", "semi-obstinate"],
        "siblings": ["Shaun Sadsarin"],
        "likely_pairs": ["Kate Nainggolan", "Jill Nainggolan", "Shaun Sadsarin", "Vivian Muy"],
        "likely_conflicts": ["Dylan Pastorin"],
        "emoji": "feeling_silly"
    },
    "Dylan Pastorin": {
        "age": 21, "gender": "Male",
        "traits": ["confident", "wannabe-gunner", "brash", "slow", "semi-manipulable", "extrovert"],
        "siblings": [],
        "likely_pairs": ["Noah Nainggolan", "Gabe Muy", "Shaun Sadsarin", "Vivian Muy"],
        "likely_conflicts": ["Kate Nainggolan"],
        "emoji": "approved"
    },
    "Noah Nainggolan": {
        "age": 18, "gender": "Male",
        "traits": ["spontaneous", "weeaboo", "semi-aloof", "brawler"],
        "siblings": ["Kate Nainggolan", "Jill Nainggolan"],
        "likely_pairs": ["Gabe Muy", "Jill Nainggolan", "Kate Nainggolan", "Dylan Pastorin"],
        "likely_conflicts": ["Jill Nainggolan"],
        "emoji": "sillynoah"
    },
    "Jill Nainggolan": {
        "age": 16, "gender": "Female",
        "traits": ["conniving", "demure", "mellow", "likes cookies"],
        "siblings": ["Kate Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Kate Nainggolan", "Noah Nainggolan", "Addison Sadsarin", "Gabe Muy"],
        "likely_conflicts": ["Noah Nainggolan"],
        "emoji": "que"
    },
    "Kate Nainggolan": {
        "age": 14, "gender": "Female",
        "traits": ["cheeky", "manipulative", "bold", "persuasive"],
        "siblings": ["Jill Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Dylan Pastorin", "Gabe Muy", "Addison Sadsarin", "Shaun Sadsarin"],
        "likely_conflicts": ["Aiden Muy"],
        "emoji": "sigma"
    },
    "Vivian Muy": {
        "age": 18, "gender": "Female",
        "traits": ["wise", "calm", "insightful", "secret genius"],
        "siblings": ["Gabe Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Dylan Pastorin", "Ella Muy", "Aiden Muy", "Addison Sadsarin"],
        "likely_conflicts": ["Gabe Muy"],
        "emoji": "leshame"
    },
    "Gabe Muy": {
        "age": 17, "gender": "Male",
        "traits": ["wrestler", "peacekeeper", "withdraws under pressure", "light-weight"],
        "siblings": ["Vivian Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Aiden Muy", "Nico Muy", "Shaun Sadsarin", "Noah Nainggolan"],
        "likely_conflicts": ["Addison Sadsarin"],
        "emoji": "zesty"
    },
    "Aiden Muy": {
        "age": 14, "gender": "Male",
        "traits": ["crafty", "short", "observant", "chef"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Shaun Sadsarin", "Jordan", "Nico Muy", "Addison Sadsarin"],
        "likely_conflicts": ["Ella Muy"],
        "emoji": "aidun"
    },
    "Ella Muy": {
        "age": 11, "gender": "Female",
        "traits": ["physically reliant", "luckiest"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Nico Muy"],
        "likely_pairs": ["Addison Sadsarin", "Jill Nainggolan", "Kate Nainggolan", "Vivian Muy"],
        "likely_conflicts": ["Shaun Sadsarin"],
        "emoji": "ellasigma"
    },
    "Nico Muy": {
        "age": 12, "gender": "Male",
        "traits": ["daring", "comical", "risk-taker", "needs guidance"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Ella Muy"],
        "likely_pairs": ["Jordan", "Aiden Muy", "Gabe Muy", "Shaun Sadsarin"],
        "likely_conflicts": ["Vivian Muy"],
        "emoji": "sips_milk"
    },
    "Jordan": {
        "age": 13, "gender": "Male",
        "traits": ["easy-going", "quietly skilled", "funny"],
        "siblings": [],
        "likely_pairs": ["Nico Muy", "Gabe Muy", "Aiden Muy", "Dylan Pastorin"],
        "likely_conflicts": ["Dylan Pastorin"],
        "emoji": "agua"
    }
}
CHARACTERS = list(CHARACTER_INFO.keys())

# Game State
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
        self.game_speed = 1.0
        self.save_file = f"zombie_game_{initiator}.json"

    def save(self):
        """Save game state to file"""
        data = {
            "initiator": self.initiator,
            "round": self.round,
            "alive": self.alive,
            "dead": self.dead,
            "last_choice": self.last_choice,
            "last_events": self.last_events,
            "options": self.options,
            "votes": dict(self.votes),
            "stats": {k: dict(v) for k, v in self.stats.items()},
            "story_seed": self.story_seed,
            "story_context": self.story_context,
            "round_number": self.round_number,
            "game_speed": self.game_speed
        }
        with open(self.save_file, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, initiator: int):
        """Load game state from file"""
        save_file = f"zombie_game_{initiator}.json"
        if not os.path.exists(save_file):
            return None
            
        with open(save_file, 'r') as f:
            data = json.load(f)
        
        game = cls(data["initiator"])
        game.round = data["round"]
        game.alive = data["alive"]
        game.dead = data["dead"]
        game.last_choice = data["last_choice"]
        game.last_events = data["last_events"]
        game.options = data["options"]
        game.votes = data["votes"]
        game.stats = {k: defaultdict(int, v) for k, v in data["stats"].items()}
        game.story_seed = data["story_seed"]
        game.story_context = data["story_context"]
        game.round_number = data["round_number"]
        game.game_speed = data.get("game_speed", 1.0)
        
        return game

    def delete_save(self):
        """Delete the save file"""
        if os.path.exists(self.save_file):
            os.remove(self.save_file)

def end_game():
    global active_game
    if active_game:
        active_game.terminated = True
        active_game.delete_save()
        active_game = None

def is_active():
    return active_game is not None and not active_game.terminated

def get_delay(delay_type):
    """Get delay based on current speed setting"""
    speed_settings = SPEED_SETTINGS.get(current_speed, SPEED_SETTINGS[1.0])
    return speed_settings.get(delay_type, 1.0)

async def generate_unique_setting():
    messages = [
        {"role": "system", "content": "You are a horror storyteller."},
        {"role": "user", "content": "🎬 Generate a unique setting for a zombie survival story. Be vivid, eerie, and specific. Avoid generic locations. Describe the environment in one sentence."}
    ]
    return await generate_ai_text(messages)

async def start_game_async(user_id: int, resume=False):
    global active_game, current_speed
    
    if resume:
        # Try to load existing game
        active_game = GameState.load(user_id)
        if active_game:
            current_speed = active_game.game_speed
            return True
        return False
    
    # Start new game
    active_game = GameState(user_id)
    current_speed = active_game.game_speed
    active_game.story_seed = await generate_unique_setting()
    active_game.story_context = f"Setting: {active_game.story_seed}\n"
    return True

# Formatting
def bold_name(name: str) -> str:
    return f"**{name}**"

def bold_character_names(text: str) -> str:
    # First handle possessive forms
    for name in CHARACTER_INFO:
        possessive_pattern = rf"\b({re.escape(name)})'s\b"
        text = re.sub(possessive_pattern, r"**\1**'s", text)
    
    # Then handle regular names (process longer names first to avoid partial matches)
    sorted_names = sorted(CHARACTER_INFO.keys(), key=len, reverse=True)
    for name in sorted_names:
        # Use negative lookbehind and lookahead to avoid matching already bolded text
        name_pattern = rf"(?<!\*)\b({re.escape(name)})\b(?!\*)"
        text = re.sub(name_pattern, r"**\1**", text)
    
    return text

def format_bullet(text: str) -> str:
    text = text.strip().lstrip('•-').strip()
    # Ensure proper punctuation
    if not text.endswith(('.', '!', '?', '…', '"')):
        text += '.'
    return f"• {text}"

def capitalize_first_letter(text: str) -> str:
    """Capitalize the first letter of a string"""
    if not text:
        return text
    return text[0].upper() + text[1:] if len(text) > 1 else text.upper()

def split_into_sentences(text: str) -> list:
    return re.split(r'(?<=[.!?])\s+', text.strip())

def enforce_bullets(text: str) -> list:
    lines = text.splitlines()
    bullets = []
    current = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        # Clean up bullet markers
        if stripped.startswith(('•', '-', '*')):
            stripped = stripped[1:].strip()
        
        contains_name = any(name.split()[0] in stripped for name in CHARACTER_INFO)
        
        if contains_name or (current and len(current) > 100):
            if current:
                bullets.append(f"• {bold_character_names(current.strip())}")
                current = ""
            bullets.append(f"• {bold_character_names(stripped)}")
        else:
            if current:
                current += " " + stripped
            else:
                current = stripped

    if current:
        bullets.append(f"• {bold_character_names(current.strip())}")

    return bullets

async def stream_bullets_in_message(
    channel: discord.TextChannel,
    bullets: list,
    delay_type: str = "scene"
):
    """Stream bullets with proper formatting and emoji support"""
    delay = get_delay(delay_type)
    
    # Filter out empty bullets
    bullets = [b for b in bullets if b.strip() and b.strip() != "•"]
    
    if not bullets:
        return
    
    try:
        msg = await channel.send("...")
    except Exception as e:
        logger.warning(f"Initial message failed: {e}")
        # Fallback: send all at once
        content = "\n".join(bullets)
        await channel.send(content)
        return

    content = ""
    for i, bullet in enumerate(bullets):
        cleaned = bullet.strip()
        if not cleaned:
            continue
        
        # Ensure bullet ends with punctuation for clean spacing
        if not cleaned.endswith(('.', '!', '?', '"', '…', '...')):
            cleaned += "."
        
        content += f"{cleaned}\n\n"  # Double line break for dramatic spacing
        
        try:
            await msg.edit(content=content.strip())
        except Exception as e:
            logger.warning(f"Edit failed during bullet stream: {cleaned} — {e}")
            # Fallback: send remaining as new message
            remaining = bullets[i:]
            if remaining:
                await channel.send("\n".join(remaining))
            return
    
        await asyncio.sleep(delay)

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

# Prompt Builders
def build_scene_prompt():
    g = active_game
    traits = "\n".join([
        f"{bold_name(n)}: {', '.join(CHARACTER_INFO.get(n.strip(), {}).get('traits', ['Unknown']))}"
        for n in g.alive
    ])
    return (
        "You are a text-only assistant. Do not generate or suggest images under any circumstances. "
        "Keep scenes concise - maximum 6-8 short bullet points. Each bullet should be 1-2 sentences max."
        "Do not speak as an assistant. Do not offer help, commentary, or meta-observations. Stay fully in-character and in-world."
        "The world has fallen to a zombie outbreak. The youthful survivors are hunted, exhausted, and emotionally frayed. Every scene continues their desperate struggle against the undead and each other."
        "Respond only with narrative, dialogue, and bullet-pointed text.\n\n"
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join([bold_name(n) for n in g.alive])}\n"
        f"💀 Dead: {', '.join([bold_name(n) for n in g.dead])}\n"
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
        "CAPITALIZE the first letter of each description (e.g., 'Alert, tense' not 'alert, tense')."
        "Do not speak as an assistant. Do not offer help, commentary, or meta-observations. Stay fully in-character and in-world."
        "Format each as a bullet point using •."
        "After the bullets, describe the ambient atmosphere in a brief sentence. Do not merge character traits with narration. This should also be its own bullet."
        "Do not include dead characters."
        "Do not revive dead characters."
    )

def build_group_dynamics_prompt():
    g = active_game
    return (
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join(g.alive)}\n\n"
        "Summarize the current group dynamics in 3–5 bullet points. Focus only on notable relationship shifts: emerging bonds and rising tensions. Avoid listing every character. Do not repeat previous dynamics unless they've evolved. Keep each bullet short and emotionally resonant."
        "Format each as a bullet point using • without dashes or extra symbols."
    )

def build_dilemma_prompt(scene_text, health_text):
    return (
        f"{active_game.story_context}\n"
        f"Scene:\n{scene_text}\n\n"
        f"Health:\n{health_text}\n\n"
        "🧠 Describe a new problem that arises, specific to this situation. "
        "Do not include any choices or options. Only describe the situation."
        "Format as exactly two bullet points using • without dashes."
    )

def build_choices_prompt(dilemma_text):
    return (
        f"{active_game.story_context}\n"
        f"Dilemma:\n{dilemma_text}\n\n"
        "Based on the current scene, list exactly 2 distinct choices the survivors could make next. Format each as a bullet point. Do not continue the story or describe what characters already did. These are branching options for the players to choose from."
        "Format each as a numbered bullet starting with '1.' and '2.'."
    )

# AI Generators
async def generate_scene(g):
    raw_scene = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating cinematic zombie survival scenes. Keep scenes concise - maximum 6-8 short bullet points."},
        {"role": "user", "content": build_scene_prompt()}
    ])
    auto_track_deaths(raw_scene, g)
    # ⚠️ Validate that narration matches game state
    for name in g.alive:
        if name in raw_scene and any(word in raw_scene.lower() for word in [
            "dies", "killed", "slumps", "blood", "screams", "dragged", "crushed", "torn", "bitten", "devoured"
        ]):
            logger.warning(f"⚠️ Mismatch: {name} described as dead but marked alive.")
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
        {"role": "system", "content": "You are a horror narrator generating a health report. CAPITALIZE the first letter of each health description."},
        {"role": "user", "content": build_health_prompt()}
    ])
    auto_track_stats(raw_health, g)
    return raw_health

async def generate_group_dynamics(g):
    raw_dynamics = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator describing group dynamics. Use simple bullet points without dashes."},
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
            "Only output text in bullet-point format without dashes."
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

        # Check for existing game
        existing_game = GameState.load(ctx.author.id)
        if existing_game:
            view = discord.ui.View()
            continue_btn = discord.ui.Button(label="Continue", style=discord.ButtonStyle.green)
            new_btn = discord.ui.Button(label="New Game", style=discord.ButtonStyle.red)
            
            async def continue_callback(interaction):
                global active_game, current_speed
                active_game = existing_game
                current_speed = active_game.game_speed
                await interaction.response.edit_message(content="🔄 Continuing previous game...", view=None)
                await self.run_round(ctx.channel)
                
            async def new_callback(interaction):
                await interaction.response.edit_message(content="🔄 Starting new game...", view=None)
                await start_game_async(ctx.author.id)
                await self.run_round(ctx.channel)
                
            continue_btn.callback = continue_callback
            new_btn.callback = new_callback
            view.add_item(continue_btn)
            view.add_item(new_btn)
            
            await ctx.send("Found a previous game... Continue or Start new?", view=view)
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

        # Check for existing game
        existing_game = GameState.load(interaction.user.id)
        if existing_game:
            view = discord.ui.View()
            continue_btn = discord.ui.Button(label="Continue", style=discord.ButtonStyle.green)
            new_btn = discord.ui.Button(label="New Game", style=discord.ButtonStyle.red)
            
            async def continue_callback(interaction):
                global active_game, current_speed
                active_game = existing_game
                current_speed = active_game.game_speed
                await interaction.response.edit_message(content="🔄 Continuing previous game...", view=None)
                await self.run_round(interaction.channel)
                
            async def new_callback(interaction):
                await interaction.response.edit_message(content="🔄 Starting new game...", view=None)
                await start_game_async(interaction.user.id)
                await self.run_round(interaction.channel)
                
            continue_btn.callback = continue_callback
            new_btn.callback = new_callback
            view.add_item(continue_btn)
            view.add_item(new_btn)
            
            await interaction.followup.send("Found a previous game... Continue or Start new?", view=view)
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

    @commands.command(name="speed")
    async def speed_legacy(self, ctx: commands.Context, speed: float = None):
        global current_speed
        
        if not is_active():
            await ctx.send("⚠️ No active zombie game to adjust speed.")
            return
            
        if speed is None:
            await ctx.send(f"⚡ Current game speed: {current_speed}x")
            return
            
        if speed not in [1.0, 1.5, 2.0]:
            await ctx.send("⚠️ Invalid speed. Use 1.0, 1.5, or 2.0")
            return
            
        current_speed = speed
        active_game.game_speed = speed
        active_game.save()
        await ctx.send(f"⚡ Game speed set to {speed}x")

    @app_commands.command(name="speed", description="Adjust game speed")
    @app_commands.describe(speed="Game speed multiplier")
    async def speed_slash(self, interaction: Interaction, speed: float):
        global current_speed
        
        if not is_active():
            await interaction.response.send_message("⚠️ No active zombie game to adjust speed.", ephemeral=True)
            return
            
        if speed not in [1.0, 1.5, 2.0]:
            await interaction.response.send_message("⚠️ Invalid speed. Use 1.0, 1.5, or 2.0", ephemeral=True)
            return
            
        current_speed = speed
        active_game.game_speed = speed
        active_game.save()
        await interaction.response.send_message(f"⚡ Game speed set to {speed}x")

    async def run_round(self, channel: discord.TextChannel):
        if not active_game or active_game.terminated:
            await channel.send("🛑 Game has been terminated.")
            return
            
        g = active_game
        g.round += 1
        
        if g.terminated:
            await channel.send("🛑 Game has been terminated.")
            return

        # Save game state at start of round
        g.save()

        # Phase 1: Scene
        raw_scene = await generate_scene(g)
        if not raw_scene:
            await channel.send("⚠️ Scene generation failed.")
            return
            
        # Clean up scene formatting
        scene_text = raw_scene
        scene_bullets = []
        
        for line in scene_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Clean up bullet markers
            if line.startswith(('•', '-', '*')):
                line = line[1:].strip()
                
            if line:
                scene_bullets.append(f"• {bold_character_names(line)}")

        # Stream scene bullets
        await channel.send(f"━━━━━━━━━━━━━━\n🎭 **Scene {g.round_number}**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, scene_bullets, "scene")

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

        # Process health report with custom emojis for ALL characters
        health_lines = []
        processed_characters = set()

        for line in raw_health.split('\n'):
            if not line.strip() or not line.strip().startswith('•'):
                continue
                
            line = line.strip().lstrip('•').strip()
            
            # Try to find which character this line refers to
            matched_character = None
            for name in g.alive:
                if name in line and name not in processed_characters:
                    matched_character = name
                    processed_characters.add(name)
                    break
            
            if matched_character:
                # Extract health status (everything after the character name)
                health_status = line.replace(matched_character, '').strip().lstrip(':').strip()
                
                # Capitalize first letter
                health_status = capitalize_first_letter(health_status)
                
                # Determine health tier icon
                if any(word in health_status.lower() for word in ['healthy', 'good', 'strong', 'fine', 'well']):
                    icon = "🟢"
                elif any(word in health_status.lower() for word in ['hurt', 'wounded', 'injured', 'weak', 'tired', 'exhausted']):
                    icon = "🟡"
                elif any(word in health_status.lower() for word in ['critical', 'dying', 'bleeding', 'unconscious', 'fever']):
                    icon = "🔴"
                else:
                    icon = "🟢"  # Default to green
                
                # Format with proper spacing for emojis
                emoji_name = CHARACTER_INFO[matched_character]["emoji"]
                emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
                if emoji:
                    formatted_line = f"{icon} {bold_name(matched_character)} {emoji} - {health_status}"
                else:
                    formatted_line = f"{icon} {bold_name(matched_character)} :{emoji_name}: - {health_status}"
                health_lines.append(formatted_line)
            else:
                # Line doesn't contain a character name, add as-is
                health_lines.append(f"• {capitalize_first_letter(line)}")

        # Add any missing characters
        for name in g.alive:
            if name not in processed_characters:
                emoji_name = CHARACTER_INFO[name]["emoji"]
                emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
                if emoji:
                    health_lines.append(f"🟢 {bold_name(name)} {emoji} - Status unknown")
                else:
                    health_lines.append(f"🟢 {bold_name(name)} :{emoji_name}: - Status unknown")

        await channel.send("━━━━━━━━━━━━━━\n🩺 **Health Status**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, health_lines, "health")

        # Phase 3b: Group Dynamics
        raw_dynamics = await generate_group_dynamics(g)
        if raw_dynamics:
            # Clean up dynamics formatting
            dynamics_bullets = []
            for line in raw_dynamics.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Clean up bullet markers and dashes
                if line.startswith(('•', '-', '*')):
                    line = line[1:].strip()
                line = line.lstrip('-').strip()
                
                if line:
                    # Add emojis to character names in dynamics
                    formatted_line = bold_character_names(line)
                    for name, info in CHARACTER_INFO.items():
                        if name in line and name in g.alive:
                            emoji_name = info["emoji"]
                            emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
                            if emoji:
                                formatted_line = formatted_line.replace(bold_name(name), f"{bold_name(name)} {emoji}")
                            else:
                                formatted_line = formatted_line.replace(bold_name(name), f"{bold_name(name)} :{emoji_name}:")
                    dynamics_bullets.append(f"• {formatted_line}")

            await channel.send("━━━━━━━━━━━━━━\n💬 **Group Dynamics**\n━━━━━━━━━━━━━━")
            await stream_bullets_in_message(channel, dynamics_bullets, "dynamics")

        # Phase 4: Dilemma
        raw_dilemma = await generate_dilemma(raw_scene, raw_health, g)
        if not raw_dilemma:
            await channel.send("⚠️ Dilemma generation failed.")
            return

        # Clean up dilemma formatting
        dilemma_bullets = []
        for line in raw_dilemma.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Clean up bullet markers and dashes
            if line.startswith(('•', '-', '*')):
                line = line[1:].strip()
            line = line.lstrip('-').strip()
            
            if line and not any(line.startswith(x) for x in ['A.', 'B.', 'C.', 'D.', 'E.', 'F.', 'What do you do?']):
                dilemma_bullets.append(f"• {bold_character_names(line)}")

        await channel.send(f"━━━━━━━━━━━━━━\n🧠 **Dilemma – Round {g.round_number}**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, dilemma_bullets, "dilemma")

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
        await stream_bullets_in_message(channel, g.options, "choices")

        choices_msg = await channel.send("━━━━━━━━━━━━━━\n🗳️ React to vote!")
        await choices_msg.add_reaction("1️⃣")
        await choices_msg.add_reaction("2️⃣")
        
        # Voting with early termination - affected by speed modifier
        countdown_duration = int(20 / current_speed)  # Adjust countdown based on speed
        countdown_msg = await channel.send(f"⏳ Voting ends in {countdown_duration} seconds...")
        start_time = datetime.utcnow()
        last_vote_time = start_time
        votes_cast = set()
        early_termination = False
        
        # Check for votes every second, with early termination
        for i in range(countdown_duration, 0, -1):
            if active_game and active_game.terminated:
                return
                
            # Refresh message to get current reactions
            try:
                choices_msg = await channel.fetch_message(choices_msg.id)
                votes = await tally_votes(choices_msg, votes_cast)
                
                # Check if we have votes and if it's been 5 seconds since last vote
                current_time = datetime.utcnow()
                if (votes["1️⃣"] > 0 or votes["2️⃣"] > 0) and (current_time - last_vote_time).total_seconds() >= 5:
                    early_termination = True
                    break
                    
                # Update last vote time if we got new votes
                if votes["1️⃣"] + votes["2️⃣"] > 0:
                    last_vote_time = current_time
                    
            except Exception as e:
                logger.warning(f"Error fetching votes: {e}")
                
            # Update countdown
            try:
                await countdown_msg.edit(content=f"⏳ Voting ends in {i} seconds...")
            except Exception as e:
                logger.warning(f"Error updating countdown: {e}")
                
            await asyncio.sleep(1)

        # Final vote tally
        try:
            choices_msg = await channel.fetch_message(choices_msg.id)
            votes = await tally_votes(choices_msg, votes_cast)
            
            # Update countdown message to show voting has finished
            if early_termination:
                await countdown_msg.edit(content="✅ Voting completed early (5 seconds without new votes)")
            else:
                await countdown_msg.edit(content="✅ Voting period ended")
                
        except Exception as e:
            logger.warning(f"Error fetching final votes: {e}")
            votes = {"1️⃣": 0, "2️⃣": 0}

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

        await channel.send(f"━━━━━━━━━━━━━━━━━━━━━━━\n     🩸 End of Round {g.round} 🩸\n━━━━━━━━━━━━━━━━━━━━━━━")

        # Process outcome bullets
        outcome_bullets = []
        for line in outcome_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith(('•', '-', '*')):
                line = line[1:].strip()
                
            if line:
                outcome_bullets.append(f"• {bold_character_names(line)}")

        # NOW ask the AI to explicitly list deaths in a structured way
        death_detection_prompt = (
            f"STORY OUTCOME:\n{raw_outcome}\n\n"
            f"CURRENT ALIVE CHARACTERS: {', '.join(g.alive)}\n\n"
            "Analyze this story outcome and list ONLY the names of characters who definitely died. "
            "Return the names in this exact format: \n"
            "DIED: Name1, Name2, Name3\n\n"
            "If no characters died, return: \n"
            "DIED: None\n\n"
            "Be strict - only include characters who clearly died in the narrative."
        )
        
        death_analysis = await generate_ai_text([
            {"role": "system", "content": "You are an analyst identifying character deaths from story text."},
            {"role": "user", "content": death_detection_prompt}
        ], temperature=0.3)  # Low temperature for consistent formatting
        
        # Parse the AI's death analysis
        new_deaths = []
        if death_analysis:
            died_match = re.search(r"DIED:\s*(.+?)(?:\n|$)", death_analysis, re.IGNORECASE)
            if died_match:
                deaths_text = died_match.group(1).strip()
                if deaths_text.lower() != "none":
                    # Parse the death names
                    death_names = [name.strip() for name in deaths_text.split(",")]
                    for death_name in death_names:
                        # Find matching character
                        for char_name in g.alive[:]:
                            if char_name.lower() == death_name.lower():
                                g.alive.remove(char_name)
                                g.dead.append(char_name)
                                new_deaths.append(char_name)
                                logger.info(f"☠️ {char_name} marked dead from AI death analysis")
        
        g.dead.extend(new_deaths)

        # Fallback: ensure we don't lose all survivors
        if not g.alive and new_deaths:
            # Revive one random character as fallback
            revived = random.choice(new_deaths)
            g.alive.append(revived)
            g.dead.remove(revived)
            logger.warning(f"⚠️ No survivors listed — reviving {revived} as fallback.")

        # Format survivors list with emojis
        formatted_survivors = []
        for name in g.alive:
            emoji_name = CHARACTER_INFO.get(name, {}).get("emoji", "")
            # Try to get the actual emoji object from the server
            emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
            if emoji:
                formatted_survivors.append(f"• {bold_name(name)} {emoji}")
            else:
                formatted_survivors.append(f"• {bold_name(name)} :{emoji_name}:")

        if not outcome_bullets:
            await channel.send("⚠️ No outcome narration was generated.")
            return
        
        await channel.send("━━━━━━━━━━━━━━\n📘 **Outcome**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, outcome_bullets, "summary")
            
        narration_only = raw_scene
        g.story_context += narration_only + "\n"

        # Format deaths with emojis like survivors
        formatted_deaths = []
        for name in new_deaths:
            emoji_name = CHARACTER_INFO.get(name, {}).get("emoji", "")
            # Try to get the actual emoji object from the server
            emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
            if emoji:
                formatted_deaths.append(f"• {bold_name(name)} {emoji}")
            else:
                formatted_deaths.append(f"• {bold_name(name)} :{emoji_name}:")

        await channel.send("━━━━━━━━━━━━━━\n💀 **Deaths This Round**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, formatted_deaths, "stats")
        
        await channel.send("━━━━━━━━━━━━━━\n🧍 **Remaining Survivors**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(channel, formatted_survivors, "stats")

        if len(g.alive) <= 1:
            if len(g.alive) == 1:
                survivor = g.alive[0]
                emoji = CHARACTER_INFO.get(survivor, {}).get("emoji", "")
                await channel.send(f"🏆 {bold_name(survivor)} :{emoji}: is the sole survivor!")
            else:
                await channel.send("💀 No survivors remain.")
            await self.end_summary(channel)
            end_game()
            return

        g.round_number += 1
        await self.run_round(channel)

    async def end_summary(self, channel: discord.TextChannel):
        g = active_game
        if not g or g.terminated:
            return  # Don't proceed if game is already terminated
        
        await channel.send("━━━━━━━━━━━━━━\n📜 **Game Summary**\n━━━━━━━━━━━━━━")
    
        valid_deaths = [name for name in g.dead if name and name.lower() != "none"]
        # Format deaths with emojis
        deaths_block = []
        for name in valid_deaths:
            emoji_name = CHARACTER_INFO.get(name, {}).get("emoji", "")
            emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
            if emoji:
                deaths_block.append(f"• {bold_name(name)} {emoji}")
            else:
                deaths_block.append(f"• {bold_name(name)} :{emoji_name}:")
    
        if not deaths_block:
            deaths_block = ["• None"]
        await channel.send("🪦 **Deaths (most recent first)**")
        await stream_bullets_in_message(channel, deaths_block, "stats")
    
        def safe_top(stat_dict):
            return max(stat_dict.items(), key=lambda x: x[1])[0] if stat_dict else "None"
    
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
        await stream_bullets_in_message(channel, final_stats, "stats")
    
        # Only generate recap if game wasn't manually terminated mid-round
        if g.story_context and g.last_choice:
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
            if raw_summary:
                summary_bullets = [
                    format_bullet(bold_character_names(line.lstrip("•").strip()))
                    for line in raw_summary.splitlines()
                    if line.strip() and line.strip() != "•"
                ]
                await channel.send("🧠 **Scene Summary**")
                await stream_bullets_in_message(channel, summary_bullets, "summary")
            else:
                await channel.send("📝 *No AI recap generated due to manual termination*")
        else:
            await channel.send("📝 *Game ended manually before any story developed*")
        
        await channel.send("🎬 Thanks for surviving (or not) the zombie apocalypse. Until next time...")

# Utilities
def auto_track_deaths(raw_scene: str, g):
    bullets = raw_scene.split("•")[1:]  # Skip the empty first split

    for bullet in bullets:
        cleaned = bullet.strip().lower()
        for name in g.alive[:]:  # Copy to avoid mutation
            if re.search(rf"\b{name.lower()}\b", cleaned):
                if any(phrase in cleaned for phrase in [
                    "vanish", "dragged under", "pulled beneath", "final breath", "crushed", "dissolved",
                    "slumps", "sinks", "submerged", "yanked", "gone", "lost", "devoured", "bitten", "torn",
                    "dies", "killed", "death", "dead", "perish", "succumb"
                ]) or cleaned.endswith(("slumps.", "vanishes.", "is gone.", "is lost.", "is dragged under.", "is crushed.", "dies.")):
                    g.dead.append(name)
                    g.alive.remove(name)
                    print(f"☠️ {name} marked dead based on bullet: {bullet.strip()}")

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
        if re.search(rf"{name}.*(help|assist|protect|save|heal|aid|support)", text, re.IGNORECASE):
            g.stats["helped"][name] += 1
        if re.search(rf"{name}.*(improvise|solve|navigate|strategize|craft|build|repair|scavenge|plan)", text, re.IGNORECASE):
            g.stats["resourceful"][name] += 1
        if re.search(rf"{name}.*(betray|attack|abandon|sabotage|threaten|steal|harm|endanger)", text, re.IGNORECASE):
            g.stats["sinister"][name] += 1
        if re.search(rf"{name}.*(grace|sacrifice|honor|calm|composure|dignity|bravery|courage)", text, re.IGNORECASE):
            g.stats["dignified"][name] += 1

def auto_track_relationships(text: str, g):
    if not text:
        return
    for name1 in g.alive:
        for name2 in g.alive:
            if name1 == name2:
                continue
            if re.search(rf"{name1}.*(share|nod|exchange|trust|help|protect|comfort|support).+{name2}", text, re.IGNORECASE):
                g.stats["bonds"][(name1, name2)] += 1
            if re.search(rf"{name1}.*(argue|fight|oppose|resent|blame|distrust|confront|attack).+{name2}", text, re.IGNORECASE):
                g.stats["conflicts"][(name1, name2)] += 1

def get_top_stat(stat_dict):
    return max(stat_dict.items(), key=lambda x: x[1])[0] if stat_dict else "None"

async def tally_votes(message, votes_cast):
    votes = {"1️⃣": 0, "2️⃣": 0}
    for reaction in message.reactions:
        if reaction.emoji in votes:
            users = [user async for user in reaction.users()]
            for user in users:
                if not user.bot and user.id not in votes_cast:
                    votes[reaction.emoji] += 1
                    votes_cast.add(user.id)
    return votes

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    print("✅ ZombieGame cog loaded")
