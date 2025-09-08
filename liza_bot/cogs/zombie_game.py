import os
import re
import httpx
import asyncio
import logging
import discord
import random
import json
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from discord.ext import commands
from discord import Interaction, app_commands
from collections import defaultdict

# --- Constants ---
VERSION = "2.2.0"  # Updated version
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zombie_game")
load_dotenv()

# --- Game Configuration ---
ZOMBIE_CHANNEL_ID = int(os.getenv("ZOMBIE_CHANNEL_ID", "0"))
MODEL = os.getenv("MODEL")
OPENROUTER_API_KEYS = [key for key in [
    os.getenv("OPENROUTER_API_KEY_1"),
    os.getenv("OPENROUTER_API_KEY_2"),
    os.getenv("OPENROUTER_API_KEY_3"),
    os.getenv("OPENROUTER_API_KEY_4"),
    os.getenv("OPENROUTER_API_KEY_5"),
    os.getenv("OPENROUTER_API_KEY_6"),
    os.getenv("OPENROUTER_API_KEY_7"),
] if key]

# --- Game Speed Settings ---
SPEED_SETTINGS = {
    1.0: {"scene": 4.7, "health": 2.0, "dynamics": 3.5, "dilemma": 5.0, "choices": 4.5, "summary": 4.5, "stats": 4.5},
    1.5: {"scene": 3.1, "health": 1.3, "dynamics": 2.3, "dilemma": 3.3, "choices": 3.0, "summary": 3.0, "stats": 3.0},
    2.0: {"scene": 2.4, "health": 1.0, "dynamics": 1.8, "dilemma": 2.5, "choices": 2.3, "summary": 2.3, "stats": 2.3}
}

# --- Character Data ---
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
        "traits": ["wrestler", "peacekeeper", "humorous", "light-weight"],
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

# --- Game State ---
class GameState:
    def __init__(self, initiator: int, game_mode: str = "player"):
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
        self.game_mode = game_mode
        self.save_file = f"zombie_game_{initiator}.json"

    def save(self):
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
            "game_speed": self.game_speed,
            "game_mode": self.game_mode
        }
        with open(self.save_file, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, initiator: int):
        save_file = f"zombie_game_{initiator}.json"
        if not os.path.exists(save_file):
            return None
        with open(save_file, 'r') as f:
            data = json.load(f)
        game = cls(data["initiator"], data.get("game_mode", "player"))
        game.round = data["round"]
        game.alive = data["alive"]
        game.dead = list(dict.fromkeys(data["dead"]))
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
        if os.path.exists(self.save_file):
            os.remove(self.save_file)

    def save_to_leaderboard(self, winner=None):
        try:
            conn = sqlite3.connect('zombie_leaderboard.db')
            c = conn.cursor()
            c.execute("INSERT INTO games (initiator, winner) VALUES (?, ?)", (self.initiator, winner))
            game_id = c.lastrowid
            for char in CHARACTERS:
                survived = char in self.alive
                death_round = self.round if not survived else None
                c.execute('''INSERT INTO character_stats
                            (character_name, game_id, death_round, survived)
                            VALUES (?, ?, ?, ?)''',
                         (char, game_id, death_round, survived))
            for (char1, char2), bond_strength in self.stats["bonds"].items():
                if bond_strength > 0:
                    c.execute('''INSERT INTO relationships
                                (character1, character2, game_id, bond_strength)
                                VALUES (?, ?, ?, ?)''',
                             (char1, char2, game_id, bond_strength))
            for (char1, char2), conflict_strength in self.stats["conflicts"].items():
                if conflict_strength > 0:
                    c.execute('''INSERT INTO relationships
                                (character1, character2, game_id, conflict_strength)
                                VALUES (?, ?, ?, ?)''',
                             (char1, char2, game_id, conflict_strength))
            conn.commit()
            conn.close()
            logger.info("Game results saved to leaderboard")
        except Exception as e:
            logger.error(f"Error saving to leaderboard: {e}")

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect('zombie_leaderboard.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS games
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  initiator INTEGER,
                  winner TEXT,
                  completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS character_stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  character_name TEXT,
                  game_id INTEGER,
                  death_round INTEGER,
                  survived BOOLEAN,
                  FOREIGN KEY (game_id) REFERENCES games (id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS relationships
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  character1 TEXT,
                  character2 TEXT,
                  game_id INTEGER,
                  bond_strength INTEGER DEFAULT 0,
                  conflict_strength INTEGER DEFAULT 0,
                  FOREIGN KEY (game_id) REFERENCES games (id))''')
    conn.commit()
    conn.close()

init_db()

# --- AI Integration ---
async def send_openrouter_request(payload):
    tried_keys = set()
    for key in OPENROUTER_API_KEYS:
        if key in tried_keys:
            continue
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
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
                continue
            raise
    raise RuntimeError("All OpenRouter keys exhausted or invalid.")

async def generate_ai_text(messages, temperature=0.8):
    if active_game and active_game.terminated:
        return None
    payload = {"model": MODEL, "messages": messages, "temperature": temperature}
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

# --- Game Logic ---
active_game = None
current_speed = 1.0

def is_active():
    return active_game is not None and not active_game.terminated

def end_game():
    global active_game
    if active_game:
        active_game.terminated = True
        active_game.delete_save()
        active_game = None

def get_delay(delay_type):
    speed_settings = SPEED_SETTINGS.get(current_speed, SPEED_SETTINGS[1.0])
    return speed_settings.get(delay_type, 1.0)

# --- Formatting ---
def bold_name(name: str) -> str:
    return f"**{name}**"

def bold_character_names(text: str) -> str:
    all_names = []
    for name in CHARACTER_INFO.keys():
        all_names.append(name)  # Full name
        all_names.append(name.split()[0])  # First name
    all_names = sorted(set(all_names), key=len, reverse=True)

    # Handle possessives first
    for name in all_names:
        text = re.sub(rf'\b({re.escape(name)})[\'’]s\b', rf"**\1**'\2s", text)

    # Then bold full names
    for name in all_names:
        text = re.sub(rf'\b{re.escape(name)}\b', f"**{name}**", text)

    return text

def format_bullet(text: str) -> str:
    text = text.strip().lstrip('•-').strip()
    if not text.endswith(('.', '!', '?', '…', '"')):
        text += '.'
    return f"• {text}"

def capitalize_first_letter(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:] if len(text) > 1 else text.upper()

def enforce_bullets(text: str) -> list:
    lines = text.splitlines()
    bullets = []
    current = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
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

# --- AI Prompts ---
def build_scene_prompt():
    g = active_game
    traits = "\n".join([
        f"{bold_name(n)}: {', '.join(CHARACTER_INFO.get(n.strip(), {}).get('traits', ['Unknown']))}"
        for n in g.alive
    ])
    return (
        "You are a text-only assistant. Do not generate or suggest images under any circumstances. "
        "Keep scenes concise - maximum 6-8 short bullet points. Each bullet should be 1-2 sentences max. "
        "Do not speak as an assistant. Do not offer help, commentary, or meta-observations. "
        "The world has fallen to a zombie outbreak. The youthful survivors are hunted, exhausted, and emotionally frayed. "
        "Every scene continues their desperate struggle against the undead and each other. "
        "Respond only with narrative, dialogue, and bullet-pointed text.\n\n"
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join([bold_name(n) for n in g.alive])}\n"
        f"💀 Dead: {', '.join([bold_name(n) for n in g.dead])}\n"
        f"🧠 Traits:\n{traits}\n\n"
        "🎬 Continue the story. Include every alive character. "
        "Format each action as a bullet point using •. Keep bullets short and on their own lines. "
        "Avoid repeating scenes or plotlines from previous sessions. "
        "Never revive characters who have died. "
        "Don't treat dead characters as alive. "
        "Do not list multiple options. Do not use numbered choices. Only continue the story. "
        "Use dialogue sparingly and format it as: • > Character: \"Dialogue\""
    )

def build_health_prompt():
    g = active_game
    alive_characters = ', '.join([f"{name.split()[0]} ({name})" for name in g.alive])
    return (
        f"{g.story_context}\n"
        f"🧍 Alive: {alive_characters}\n\n"
        "🧠 For each character listed above, describe their **physical condition** in 2–3 words. "
        "Use their **FIRST NAME** in your response (e.g., 'Shaun: Alert, focused'). "
        "CAPITALIZE the first letter of each description. "
        "Format each as a bullet point using •. "
        "**Include every alive character.** "
        "Do not use 'Status unknown' or generic descriptions."
    )

def build_scene_summary_prompt(scene_text):
    return (
        f"{active_game.story_context}\n"
        f"Scene:\n{scene_text}\n\n"
        "🧠 Summarize the key events in **one vivid sentence**. "
        "Focus on the most critical developments."
    )

# --- Game Commands ---
class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="version", description="Show the current version of the zombie game.")
    async def version(self, interaction: Interaction):
        await interaction.response.send_message(f"📌 Current version: **{VERSION}**", ephemeral=True)

    @app_commands.command(name="lizazombie", description="Start a zombie survival game")
    async def lizazombie_slash(self, interaction: Interaction):
        await interaction.response.send_message("✅ Command registered. Preparing zombie survival game...", ephemeral=True)
        if interaction.channel.id != ZOMBIE_CHANNEL_ID:
            await interaction.followup.send("❌ Run this command in the zombie channel.", ephemeral=True)
            return
        if is_active():
            await interaction.followup.send("⚠️ A zombie game is already running.", ephemeral=True)
            return
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
                await self.ask_game_mode_slash(interaction)

            continue_btn.callback = continue_callback
            new_btn.callback = new_callback
            view.add_item(continue_btn)
            view.add_item(new_btn)
            await interaction.followup.send("Found a previous game... Continue or Start new?", view=view)
            return
        await self.ask_game_mode_slash(interaction)

    async def ask_game_mode_slash(self, interaction: Interaction):
        view = discord.ui.View()
        player_btn = discord.ui.Button(label="Player Game", style=discord.ButtonStyle.blurple, emoji="👤")
        auto_btn = discord.ui.Button(label="Auto Game", style=discord.ButtonStyle.green, emoji="🤖")

        async def player_callback(interaction):
            await interaction.response.edit_message(content="🔄 Starting player game...", view=None)
            await start_game_async(interaction.user.id, "player")
            msg = await interaction.channel.send("🧟‍♀️ Zombie survival game starting in...")
            await countdown_message(msg, 3, "🧟‍♀️ Zombie survival game starting in...")
            await msg.edit(content="🧟‍♀️ Game loading...")
            logger.info("✅ Countdown finished. Starting run_round...")
            await self.run_round(interaction.channel)

        async def auto_callback(interaction):
            await interaction.response.edit_message(content="🔄 Starting auto game...", view=None)
            await start_game_async(interaction.user.id, "auto")
            msg = await interaction.channel.send("🤖 Auto zombie game starting in...")
            await countdown_message(msg, 3, "🤖 Auto zombie game starting in...")
            await msg.edit(content="🤖 Auto game loading...")
            logger.info("✅ Countdown finished. Starting run_round...")
            await self.run_round(interaction.channel)

        player_btn.callback = player_callback
        auto_btn.callback = auto_callback
        view.add_item(player_btn)
        view.add_item(auto_btn)
        await interaction.followup.send("🎮 Choose a game mode:", view=view)

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

    @app_commands.command(name="zombieleaderboard", description="Show zombie game leaderboard statistics")
    async def zombie_leaderboard_slash(self, interaction: Interaction):
        await interaction.response.defer()
        stats = get_leaderboard_stats()
        if not stats:
            await interaction.followup.send("❌ No leaderboard data available yet.")
            return
        embed = discord.Embed(
            title="🧟 Zombie Survival Leaderboard",
            description="Statistics from all completed games",
            color=0x00ff00
        )
        wins_text = "\n".join([f"{name}: {wins} wins" for name, wins in stats["wins"][:5]]) if stats["wins"] else "No wins recorded yet"
        embed.add_field(name="🏆 Most Wins", value=wins_text, inline=False)
        early_deaths_text = "\n".join([f"{name}: {deaths} early deaths" for name, deaths in stats["early_deaths"][:5]]) if stats["early_deaths"] else "No early deaths recorded yet"
        embed.add_field(name="💀 Most Early Deaths (Round 1)", value=early_deaths_text, inline=False)
        bonds_text = "\n".join([f"{char1} & {char2}: {bond}" for char1, char2, bond in stats["bonds"][:3]]) if stats["bonds"] else "No bond data yet"
        embed.add_field(name="🤝 Strongest Bonds", value=bonds_text, inline=False)
        conflicts_text = "\n".join([f"{char1} vs {char2}: {conflict}" for char1, char2, conflict in stats["conflicts"][:3]]) if stats["conflicts"] else "No conflict data yet"
        embed.add_field(name="⚔️ Biggest Conflicts", value=conflicts_text, inline=False)
        embed.set_footer(text="Play more games to see more statistics!")
        await interaction.followup.send(embed=embed)

    async def run_round(self, channel: discord.TextChannel):
        if not active_game or active_game.terminated:
            await channel.send("🛑 Game has been terminated.")
            return
        g = active_game
        g.round += 1
        if g.terminated:
            await channel.send("🛑 Game has been terminated.")
            return
        g.save()

        # --- Phase 1: Scene ---
        raw_scene = await generate_scene(g)
        if not raw_scene:
            await channel.send("⚠️ Scene generation failed.")
            return
        scene_bullets = enforce_bullets(raw_scene)

        # Generate scene summary
        raw_summary = await generate_scene_summary("\n".join(scene_bullets), g)
        if raw_summary:
            scene_bullets.append(f"\n📌 **Scene Summary**: {bold_character_names(raw_summary)}")

        await channel.send(f"=== ROUND {g.round_number} ===")
        await channel.send("🎭 **Scene**")
        await stream_bullets_in_message(channel, scene_bullets, "scene")
        g.story_context += "\n".join(scene_bullets) + "\n"
        g.story_context = "\n".join(g.story_context.strip().splitlines()[-12:])

        # --- Phase 2: Health ---
        raw_health = await generate_health_report(g)
        if not raw_health:
            await channel.send("⚠️ Health report failed.")
            return
        health_lines = []
        processed_characters = set()

        for line in raw_health.split('\n'):
            if not line.strip() or not line.strip().startswith('•'):
                continue
            line = line.strip().lstrip('•').strip()

            matched_character = None
            for name in g.alive:
                full_name = name
                first_name = name.split()[0]
                if (re.search(rf'\b{re.escape(full_name)}\b', line, re.IGNORECASE) or
                    re.search(rf'\b{re.escape(first_name)}\b', line, re.IGNORECASE)):
                    matched_character = name
                    processed_characters.add(name)
                    break

            if matched_character:
                health_status = line
                for name in g.alive:
                    full_name = name
                    first_name = name.split()[0]
                    health_status = health_status.replace(full_name, '').replace(first_name, '').strip().lstrip(':').strip()

                if health_status:
                    words = health_status.split()
                    if words:
                        words[0] = words[0].capitalize()
                        for i in range(1, len(words)):
                            words[i] = words[i].lower()
                        health_status = ' '.join(words)
                else:
                    health_status = random.choice(["Stable, cautious", "Alert, focused", "Tired, but holding on"])

                icon = "🟢"
                if any(word in health_status.lower() for word in ['hurt', 'wounded', 'injured', 'weak', 'tired', 'exhausted', 'panicked']):
                    icon = "🟡"
                elif any(word in health_status.lower() for word in ['critical', 'dying', 'bleeding', 'unconscious', 'fever', 'submerged', 'unseen']):
                    icon = "🔴"

                emoji_name = CHARACTER_INFO[matched_character]["emoji"]
                emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
                if emoji:
                    formatted_line = f"{icon} {bold_name(matched_character)} {emoji} : {health_status}"
                else:
                    formatted_line = f"{icon} {bold_name(matched_character)} :{emoji_name}: : {health_status}"
                health_lines.append(formatted_line)

        # Add missing characters with default statuses
        for name in g.alive:
            if name not in processed_characters:
                emoji_name = CHARACTER_INFO[name]["emoji"]
                emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
                default_status = random.choice(["Stable, cautious", "Alert, focused", "Tired, but holding on"])
                if emoji:
                    health_lines.append(f"🟢 {bold_name(name)} {emoji} : {default_status}")
                else:
                    health_lines.append(f"🟢 {bold_name(name)} :{emoji_name}: : {default_status}")

        await channel.send("🩺 **Health Status**")
        await stream_bullets_in_message(channel, health_lines, "health")

        # --- Phase 3: Dilemma ---
        raw_dilemma = await generate_dilemma(raw_scene, raw_health, g)
        if not raw_dilemma:
            await channel.send("⚠️ Dilemma generation failed.")
            return
        dilemma_bullets = enforce_bullets(raw_dilemma)
        await channel.send("🧠 **Dilemma**")
        await stream_bullets_in_message(channel, dilemma_bullets, "dilemma")

        # --- Phase 4: Choices ---
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
        formatted_options = [bold_character_names(option) for option in g.options]
        await channel.send("🔀 **Choices**")
        await stream_bullets_in_message(channel, formatted_options, "choices")

        # --- Phase 5: Voting ---
        if g.game_mode == "auto":
            await asyncio.sleep(get_delay("choices") * 2)
            g.last_choice = random.choice(g.options)
            await channel.send(f"🤖 **Auto-selected**: {g.last_choice}")
        else:
            choices_msg = await channel.send("🗳️ React to vote!")
            await choices_msg.add_reaction("1️⃣")
            await choices_msg.add_reaction("2️⃣")
            countdown_duration = int(20 / current_speed)
            countdown_msg = await channel.send(f"⏳ Voting ends in {countdown_duration} seconds...")
            start_time = datetime.utcnow()
            last_vote_time = start_time
            votes_cast = set()
            early_termination = False
            for i in range(countdown_duration, 0, -1):
                if active_game and active_game.terminated:
                    return
                try:
                    choices_msg = await channel.fetch_message(choices_msg.id)
                    votes = await tally_votes(choices_msg, votes_cast)
                    current_time = datetime.utcnow()
                    if (votes["1️⃣"] > 0 or votes["2️⃣"] > 0) and (current_time - last_vote_time).total_seconds() >= 5:
                        early_termination = True
                        break
                    if votes["1️⃣"] + votes["2️⃣"] > 0:
                        last_vote_time = current_time
                except Exception as e:
                    logger.warning(f"Error fetching votes: {e}")
                try:
                    await countdown_msg.edit(content=f"⏳ Voting ends in {i} seconds...")
                except Exception as e:
                    logger.warning(f"Error updating countdown: {e}")
                await asyncio.sleep(1)
            try:
                choices_msg = await channel.fetch_message(choices_msg.id)
                votes = await tally_votes(choices_msg, votes_cast)
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

        # --- Phase 6: Outcome ---
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
        outcome_bullets = enforce_bullets(raw_outcome)
        await channel.send(f"🩸 **End of Round {g.round}** 🩸")
        await stream_bullets_in_message(channel, outcome_bullets, "summary")

        # --- Phase 7: Death Detection ---
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
        ], temperature=0.3)
        new_deaths = []
        if death_analysis:
            died_match = re.search(r"DIED:\s*(.+?)(?:\n|$)", death_analysis, re.IGNORECASE)
            if died_match:
                deaths_text = died_match.group(1).strip()
                if deaths_text.lower() != "none":
                    death_names = [name.strip() for name in deaths_text.split(",")]
                    for death_name in death_names:
                        for char_name in g.alive[:]:
                            if char_name.lower() == death_name.lower():
                                if char_name not in g.dead:
                                    g.alive.remove(char_name)
                                    g.dead.append(char_name)
                                    new_deaths.append(char_name)
                                    logger.info(f"☠️ {char_name} marked dead from AI death analysis")

        # --- Ensure at least one death per round ---
        if not new_deaths and len(g.alive) > 1:
            victim = random.choice(g.alive)
            g.alive.remove(victim)
            g.dead.append(victim)
            new_deaths.append(victim)
            logger.info(f"☠️ {victim} forcibly killed to ensure death per round.")
            outcome_bullets.append(f"• {bold_name(victim)} is overwhelmed and **dies**.")

        # --- Phase 8: Survivors ---
        formatted_survivors = []
        for name in g.alive:
            emoji_name = CHARACTER_INFO.get(name, {}).get("emoji", "")
            emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
            if emoji:
                formatted_survivors.append(f"• {bold_name(name)} {emoji}")
            else:
                formatted_survivors.append(f"• {bold_name(name)} :{emoji_name}:")
        formatted_deaths = []
        for name in new_deaths:
            emoji_name = CHARACTER_INFO.get(name, {}).get("emoji", "")
            emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
            if emoji:
                formatted_deaths.append(f"• {bold_name(name)} {emoji}")
            else:
                formatted_deaths.append(f"• {bold_name(name)} :{emoji_name}:")
        await channel.send("💀 **Deaths This Round**")
        await stream_bullets_in_message(channel, formatted_deaths, "stats")
        await channel.send("🧍 **Remaining Survivors**")
        await stream_bullets_in_message(channel, formatted_survivors, "stats")

        # --- Phase 9: Game End Check ---
        if len(g.alive) <= 1:
            if len(g.alive) == 1:
                survivor = g.alive[0]
                emoji_name = CHARACTER_INFO.get(survivor, {}).get("emoji", "")
                emoji = discord.utils.get(channel.guild.emojis, name=emoji_name)
                if emoji:
                    await channel.send(f"🏆 {bold_name(survivor)} {emoji} is the sole survivor!")
                else:
                    await channel.send(f"🏆 {bold_name(survivor)} :{emoji_name}: is the sole survivor!")
                g.save_to_leaderboard(winner=survivor)
            else:
                await channel.send("💀 No survivors remain.")
                g.save_to_leaderboard()
            await self.end_summary(channel)
            end_game()
            return
        g.round_number += 1
        await self.run_round(channel)

    async def end_summary(self, channel: discord.TextChannel):
        g = active_game
        if not g or g.terminated:
            return
        await channel.send("📜 **Game Summary**")
        valid_deaths = [name for name in g.dead if name and name.lower() != "none"]
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

        most_helpful = max(g.stats.get("helped", {}).items(), key=lambda x: x[1])[0] if g.stats.get("helped") else "None"
        most_sinister = max(g.stats.get("sinister", {}).items(), key=lambda x: x[1])[0] if g.stats.get("sinister") else "None"
        most_resourceful = max(g.stats.get("resourceful", {}).items(), key=lambda x: x[1])[0] if g.stats.get("resourceful") else "None"
        most_dignified = max(g.stats.get("dignified", {}).items(), key=lambda x: x[1])[0] if g.stats.get("dignified") else "None"
        bonds = sorted(g.stats.get("bonds", {}).items(), key=lambda x: x[1], reverse=True)
        conflicts = sorted(g.stats.get("conflicts", {}).items(), key=lambda x: x[1], reverse=True)
        bond_pair = bonds[0][0] if bonds else ("None", "None")
        conflict_pair = conflicts[0][0] if conflicts else ("None", "None")
        final_stats = [
            f"🏅 Most helpful: {bold_name(most_helpful)}",
            f"😈 Most sinister: {bold_name(most_sinister)}",
            f"🔧 Most resourceful: {bold_name(most_resourceful)}",
            f"🤝 Greatest bond: {bold_name(bond_pair[0])} & {bold_name(bond_pair[1])}",
            f"⚔️ Biggest conflict: {bold_name(conflict_pair[0])} vs {bold_name(conflict_pair[1])}",
            f"🕊️ Most dignified: {bold_name(most_dignified)}"
        ]
        final_stats = [line for line in final_stats if "None" not in line]
        await channel.send("📊 **Final Stats**")
        await stream_bullets_in_message(channel, final_stats, "stats")

        if g.story_context and g.last_choice:
            raw_recap = await generate_full_recap(g)
            if raw_recap:
                recap_bullets = enforce_bullets(raw_recap)
                await channel.send("🧠 **Game Recap**")
                await stream_bullets_in_message(channel, recap_bullets, "summary")
            else:
                await channel.send("📝 *No AI recap generated*")
        else:
            await channel.send("📝 *Game ended before any story developed*")
        await channel.send("🎬 Thanks for surviving (or not) the zombie apocalypse. Until next time...")

# --- Utilities ---
async def generate_scene(g):
    raw_scene = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating cinematic zombie survival scenes."},
        {"role": "user", "content": build_scene_prompt()}
    ])
    auto_track_deaths(raw_scene, g)
    auto_track_relationships(raw_scene, g)
    return raw_scene

async def generate_scene_summary(scene_text, g):
    raw_summary = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator summarizing a zombie survival scene."},
        {"role": "user", "content": build_scene_summary_prompt(scene_text)}
    ], temperature=0.7)
    return raw_summary

async def generate_health_report(g):
    raw_health = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating a health report."},
        {"role": "user", "content": build_health_prompt()}
    ])
    auto_track_stats(raw_health, g)
    return raw_health

async def generate_dilemma(scene_text, health_text, g):
    raw_dilemma = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating dilemmas for a survival game."},
        {"role": "user", "content": (
            f"{g.story_context}\n"
            f"Scene:\n{scene_text}\n\n"
            f"Health:\n{health_text}\n\n"
            "🧠 Describe a new problem that arises, specific to this situation. "
            "Do not include any choices or options. Only describe the situation. "
            "Format as exactly two bullet points using • without dashes."
        )}
    ], temperature=0.9)
    auto_track_stats(raw_dilemma, g)
    return raw_dilemma

async def generate_choices(dilemma_text):
    raw_choices = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating voting choices."},
        {"role": "user", "content": (
            f"{active_game.story_context}\n"
            f"Dilemma:\n{dilemma_text}\n\n"
            "Based on the current scene, list exactly 2 distinct choices the survivors could make next. "
            "Format each as a numbered bullet starting with '1.' and '2.'."
        )}
    ], temperature=0.8)
    return raw_choices

async def generate_full_recap(g):
    raw_recap = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator creating a cinematic recap of an entire zombie survival story."},
        {"role": "user", "content": (
            f"Complete Story Context:\n{g.story_context}\n\n"
            f"Final Survivors: {', '.join(g.alive) if g.alive else 'None'}\n"
            f"Characters Who Died: {', '.join(g.dead) if g.dead else 'None'}\n\n"
            "🎬 Write a brief cinematic recap of the ENTIRE game story in 3-5 bullet points. "
            "Include how it began, key turning points, and how it concluded. Focus on the overall narrative arc."
        )}
    ], temperature=0.7)
    return raw_recap

def auto_track_deaths(raw_scene: str, g):
    bullets = raw_scene.split("•")[1:]
    for bullet in bullets:
        cleaned = bullet.strip().lower()
        for name in g.alive[:]:
            if re.search(rf"\b{name.lower()}\b", cleaned):
                if any(phrase in cleaned for phrase in [
                    "vanish", "dragged under", "pulled beneath", "final breath", "crushed", "dissolved",
                    "slumps", "sinks", "submerged", "yanked", "gone", "lost", "devoured", "bitten", "torn",
                    "dies", "killed", "death", "dead", "perish", "succumb"
                ]) or cleaned.endswith(("slumps.", "vanishes.", "is gone.", "is lost.", "is dragged under.", "is crushed.", "dies.")):
                    if name not in g.dead:
                        g.dead.append(name)
                        g.alive.remove(name)
                        print(f"☠️ {name} marked dead based on bullet: {bullet.strip()}")

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

def get_leaderboard_stats():
    try:
        conn = sqlite3.connect('zombie_leaderboard.db')
        c = conn.cursor()
        c.execute('''SELECT character_name, COUNT(*) as wins
                    FROM character_stats
                    WHERE survived = 1
                    GROUP BY character_name
                    ORDER BY wins DESC''')
        wins = c.fetchall()
        c.execute('''SELECT character_name, COUNT(*) as early_deaths
                    FROM character_stats
                    WHERE death_round = 1
                    GROUP BY character_name
                    ORDER BY early_deaths DESC''')
        early_deaths = c.fetchall()
        c.execute('''SELECT character1, character2, SUM(bond_strength) as total_bond
                    FROM relationships
                    WHERE bond_strength > 0
                    GROUP BY character1, character2
                    ORDER BY total_bond DESC
                    LIMIT 10''')
        bonds = c.fetchall()
        c.execute('''SELECT character1, character2, SUM(conflict_strength) as total_conflict
                    FROM relationships
                    WHERE conflict_strength > 0
                    GROUP BY character1, character2
                    ORDER BY total_conflict DESC
                    LIMIT 10''')
        conflicts = c.fetchall()
        conn.close()
        return {
            "wins": wins,
            "early_deaths": early_deaths,
            "bonds": bonds,
            "conflicts": conflicts
        }
    except Exception as e:
        logger.error(f"Error getting leaderboard stats: {e}")
        return None

async def start_game_async(user_id: int, game_mode: str = "player", resume=False):
    global active_game, current_speed
    if resume:
        active_game = GameState.load(user_id)
        if active_game:
            current_speed = active_game.game_speed
            return True
        return False
    active_game = GameState(user_id, game_mode)
    current_speed = active_game.game_speed
    active_game.story_seed = await generate_unique_setting()
    active_game.story_context = f"Setting: {active_game.story_seed}\n"
    return True

async def generate_unique_setting():
    messages = [
        {"role": "system", "content": "You are a horror storyteller."},
        {"role": "user", "content": "🎬 Generate a unique setting for a zombie survival story. Be vivid, eerie, and specific. Avoid generic locations. Describe the environment in one sentence."}
    ]
    return await generate_ai_text(messages)

async def stream_bullets_in_message(channel: discord.TextChannel, bullets: list, delay_type: str = "scene"):
    delay = get_delay(delay_type)
    bullets = [b for b in bullets if b.strip() and b.strip() != "•"]
    if not bullets:
        return
    try:
        msg = await channel.send("...")
    except Exception as e:
        logger.warning(f"Initial message failed: {e}")
        content = "\n".join(bullets)
        await channel.send(content)
        return
    content = ""
    for i, bullet in enumerate(bullets):
        cleaned = bullet.strip()
        if not cleaned:
            continue
        if not cleaned.endswith(('.', '!', '?', '"', '…', '...')):
            cleaned += "."
        content += f"{cleaned}\n\n"
        try:
            await msg.edit(content=content.strip())
        except Exception as e:
            logger.warning(f"Edit failed during bullet stream: {cleaned} — {e}")
            remaining = bullets[i:]
            if remaining:
                await channel.send("\n".join(remaining))
            return
        await asyncio.sleep(delay)

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

# --- Cog Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    print("✅ ZombieGame cog loaded")
