import os
import re
import httpx
import asyncio
import logging
import discord
import random
from dotenv import load_dotenv
from discord.ext import commands
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

def is_key_on_cooldown(key):
    return key in key_cooldowns and datetime.utcnow() < key_cooldowns[key]

def set_key_cooldown(key, seconds=600):
    key_cooldowns[key] = datetime.utcnow() + timedelta(seconds=seconds)

async def send_openrouter_request(payload):
    tried_keys = set()
    for key in OPENROUTER_API_KEYS:
        if key in tried_keys or is_key_on_cooldown(key):
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

CHARACTER_INFO = {
    "Shaun Sadsarin": {
        "age": 15,
        "gender": "Male",
        "traits": ["empathetic", "stubborn", "agile", "semi-reserved", "improviser"],
        "siblings": ["Addison Sadsarin"],
        "likely_pairs": ["Addison Sadsarin", "Aiden Muy", "Gabe Muy", "Dylan Pastorin"],
        "likely_conflicts": ["Jordan"]
    },
    "Addison Sadsarin": {
        "age": 16,
        "gender": "Female",
        "traits": ["kind", "patient", "responsible", "lacks physicality", "semi-obstinate"],
        "siblings": ["Shaun Sadsarin"],
        "likely_pairs": ["Kate Nainggolan", "Jill Nainggolan", "Shaun Sadsarin", "Vivian Muy"],
        "likely_conflicts": ["Dylan Pastorin"]
    },
    "Dylan Pastorin": {
        "age": 21,
        "gender": "Male",
        "traits": ["confident", "wannabe-gunner", "brash", "slow", "semi-manipulable", "extrovert"],
        "siblings": [],
        "likely_pairs": ["Noah Nainggolan", "Gabe Muy", "Shaun Sadsarin", "Vivian Muy"],
        "likely_conflicts": ["Kate Nainggolan"]
    },
    "Noah Nainggolan": {
        "age": 18,
        "gender": "Male",
        "traits": ["spontaneous", "weeaboo", "semi-aloof", "brawler"],
        "siblings": ["Kate Nainggolan", "Jill Nainggolan"],
        "likely_pairs": ["Gabe Muy", "Jill Nainggolan", "Kate Nainggolan", "Dylan Pastorin"],
        "likely_conflicts": ["Jill Nainggolan"]
    },
    "Jill Nainggolan": {
        "age": 16,
        "gender": "Female",
        "traits": ["conniving", "demure", "mellow", "swimmer"],
        "siblings": ["Kate Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Kate Nainggolan", "Noah Nainggolan", "Addison Sadsarin", "Gabe Muy"],
        "likely_conflicts": ["Noah Nainggolan"]
    },
    "Kate Nainggolan": {
        "age": 14,
        "gender": "Female",
        "traits": ["cheeky", "manipulative", "bold", "persuasive"],
        "siblings": ["Jill Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Dylan Pastorin", "Gabe Muy", "Addison Sadsarin", "Shaun Sadsarin"],
        "likely_conflicts": ["Aiden Muy"]
    },
    "Vivian Muy": {
        "age": 18,
        "gender": "Female",
        "traits": ["wise", "calm", "insightful", "secret genius"],
        "siblings": ["Gabe Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Dylan Pastorin", "Ella Muy", "Aiden Muy", "Addison Sadsarin"],
        "likely_conflicts": ["Gabe Muy"]
    },
    "Gabe Muy": {
        "age": 17,
        "gender": "Male",
        "traits": ["wrestler", "peacekeeper", "withdraws under pressure", "light-weight"],
        "siblings": ["Vivian Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Aiden Muy", "Nico Muy", "Shaun Sadsarin", "Noah Nainggolan"],
        "likely_conflicts": ["Addison Sadsarin"]
    },
    "Aiden Muy": {
        "age": 14,
        "gender": "Male",
        "traits": ["crafty", "short", "observant", "chef"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Shaun Sadsarin", "Jordan", "Nico Muy", "Addison Sadsarin"],
        "likely_conflicts": ["Ella Muy"]
    },
    "Ella Muy": {
        "age": 11,
        "gender": "Female",
        "traits": ["physically reliant", "luckiest"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Nico Muy"],
        "likely_pairs": ["Addison Sadsarin", "Jill Nainggolan", "Kate Nainggolan", "Vivian Muy"],
        "likely_conflicts": ["Shaun Sadsarin"]
    },
    "Nico Muy": {
        "age": 12,
        "gender": "Male",
        "traits": ["daring", "comical", "risk-taker", "needs guidance"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Ella Muy"],
        "likely_pairs": ["Jordan", "Aiden Muy", "Gabe Muy", "Shaun Sadsarin"],
        "likely_conflicts": ["Vivian Muy"]
    },
    "Jordan": {
        "age": 13,
        "gender": "Male",
        "traits": ["easy-going", "quietly skilled", "funny"],
        "siblings": [],
        "likely_pairs": ["Nico Muy", "Shaun Sadsarin", "Aiden Muy"],
        "likely_conflicts": ["Shaun Sadsarin"]
    }
}

CHARACTERS = list(CHARACTER_INFO.keys())

class GameState:
    def __init__(self, initiator: int):
        self.initiator = initiator
        self.round = 0
        self.alive = list(CHARACTERS)
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

def build_scene_prompt(g):
    traits = "\n".join([
        f"{name}: {', '.join(CHARACTER_INFO.get(name, {}).get('traits', []))}"
        for name in g.alive
    ])
    return (
        f"Setting: {g.story_seed}\n"
        f"Alive: {', '.join(g.alive)}\n"
        f"Traits:\n{traits}\n"
        "Continue the story. Focus on tension, character interactions, and eerie atmosphere. "
        "Do not include voting options or numbered choices."
    )

def format_bullet(text: str) -> str:
    return f"• {text.strip()}"

def bold_character_names(text: str) -> str:
    for name in CHARACTER_INFO:
        pattern = re.compile(rf"\b{name}\b", re.IGNORECASE)
        text = pattern.sub(f"**{name}**", text)
    return text

def enforce_bullets(text: str) -> list[str]:
    lines = text.strip().splitlines()
    return [format_bullet(line.lstrip("•").strip()) for line in lines if line.strip()]

async def stream_bullets_in_message(channel: discord.TextChannel, bullets: list[str], delay: float = 2.0):
    if not bullets:
        await channel.send("⚠️ No content to stream.")
        return

    msg = await channel.send("...")
    content = ""
    for bullet in bullets:
        content += bullet + "\n\n"
        await msg.edit(content=content.strip())
        await asyncio.sleep(delay)

async def countdown_message(channel: discord.TextChannel, seconds: int, label: str = "⏳ Time remaining"):
    msg = await channel.send(f"{label}: {seconds}s")
    for remaining in range(seconds - 1, 0, -1):
        await asyncio.sleep(1)
        await msg.edit(content=f"{label}: {remaining}s")
    await asyncio.sleep(1)
    await msg.edit(content=f"{label}: 0s")

async def collect_votes(channel: discord.TextChannel, options: list[str], timeout: int = 30):
    g = active_game
    g.votes = {}

    option_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
    await channel.send(f"🗳️ **Vote for your choice:**\n{option_text}")
    await countdown_message(channel, timeout)

    vote_counts = defaultdict(int)
    for vote in g.votes.values():
        if vote in range(1, len(options) + 1):
            vote_counts[vote] += 1

    if not vote_counts:
        await channel.send("⚠️ No votes received. Choosing randomly.")
        return random.randint(1, len(options))

    max_votes = max(vote_counts.values())
    top_choices = [choice for choice, count in vote_counts.items() if count == max_votes]
    selected = random.choice(top_choices)
    await channel.send(f"✅ Choice {selected} selected with {max_votes} votes.")
    return selected

def tally_votes():
    g = active_game
    vote_counts = defaultdict(int)
    for vote in g.votes.values():
        if vote in range(1, len(g.options) + 1):
            vote_counts[vote] += 1
    return vote_counts

def resolve_choice():
    g = active_game
    vote_counts = tally_votes()
    if not vote_counts:
        return random.randint(1, len(g.options))
    max_votes = max(vote_counts.values())
    top_choices = [choice for choice, count in vote_counts.items() if count == max_votes]
    return random.choice(top_choices)

async def finalize_round(channel: discord.TextChannel, narration: str):
    g = active_game
    if not g or g.terminated:
        await channel.send("⚠️ No active game.")
        return

    bulleted_narration = enforce_bullets(narration)

    deaths_match = re.search(r"Deaths:\s*(.+)", narration)
    survivors_match = re.search(r"Survivors:\s*(.+)", narration)

    deaths = []
    survivors = []

    if deaths_match:
        deaths = [name.strip() for name in deaths_match.group(1).split(",") if name.strip()]
    else:
        deaths = infer_deaths_from_narration(bulleted_narration)

    if survivors_match:
        survivors = [name.strip() for name in survivors_match.group(1).split(",") if name.strip()]
    else:
        survivors = [name for name in g.alive if name not in deaths]

    if not survivors and deaths:
        revived = random.choice(deaths)
        survivors = [revived]
        deaths.remove(revived)
        await channel.send(f"⚠️ No survivors listed. Reviving {revived} to avoid crash.")

    g.alive = [name for name in g.alive if name not in deaths]
    g.dead.extend([name for name in deaths if name not in g.dead])

    outcome_bullets = [
        format_bullet(bold_character_names(line.strip().lstrip("•")))
        for line in bulleted_narration
        if line.strip()
    ]

    await stream_bullets_in_message(channel, outcome_bullets, delay=3.5)

    if not g.alive:
        await channel.send("☠️ All characters have died. Game over.")
        await end_summary(channel)
        end_game()
        return

    g.round_number += 1
    await channel.send(f"✅ Round {g.round_number} complete. {len(g.alive)} survivors remain.")

async def end_summary(channel: discord.TextChannel):
    g = active_game
    if not g:
        await channel.send("⚠️ No game state found.")
        return

    top_helped = get_top_stat(g.stats["helped"])
    top_resourceful = get_top_stat(g.stats["resourceful"])
    top_sinister = get_top_stat(g.stats["sinister"])
    top_dignified = get_top_stat(g.stats["dignified"])

    bond_counts = g.stats["bonds"]
    conflict_counts = g.stats["conflicts"]

    strongest_bond = max(bond_counts.items(), key=lambda x: x[1])[0] if bond_counts else None
    strongest_conflict = max(conflict_counts.items(), key=lambda x: x[1])[0] if conflict_counts else None

    summary_lines = [
        f"🧍 Survivors: {', '.join(g.alive) if g.alive else 'None'}",
        f"☠️ Deaths: {', '.join(g.dead) if g.dead else 'None'}",
        f"🏅 Most helpful: {top_helped}" if top_helped != "None" else "",
        f"🧠 Most resourceful: {top_resourceful}" if top_resourceful != "None" else "",
        f"😈 Most sinister: {top_sinister}" if top_sinister != "None" else "",
        f"🕊️ Most dignified: {top_dignified}" if top_dignified != "None" else "",
        f"🤝 Strongest bond: {strongest_bond[0]} & {strongest_bond[1]}" if strongest_bond else "",
        f"⚔️ Strongest conflict: {strongest_conflict[0]} vs {strongest_conflict[1]}" if strongest_conflict else ""
    ]

    filtered_summary = [format_bullet(line) for line in summary_lines if line]
    await channel.send("━━━━━━━━━━━━━━\n🎬 **Final Summary**\n━━━━━━━━━━━━━━")
    await stream_bullets_in_message(channel, filtered_summary, delay=2.5)

def get_top_stat(stat_dict: dict[str, int]) -> str:
    if not stat_dict:
        return "None"
    max_value = max(stat_dict.values())
    top_entries = [name for name, value in stat_dict.items() if value == max_value]
    return random.choice(top_entries) if top_entries else "None"

def infer_deaths_from_narration(bullets: list[str]) -> list[str]:
    deaths = []
    for line in bullets:
        lowered = line.lower()
        if any(kw in lowered for kw in ["dies", "killed", "devoured", "torn apart", "bleeds out", "screams fade"]):
            for name in CHARACTER_INFO:
                if re.search(rf"\b{name}\b", line, re.IGNORECASE):
                    deaths.append(name)
    return list(set(deaths))

class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        logger.info("✅ ZombieGame cog loaded")

    @app_commands.command(name="lizazombie", description="Start a zombie survival game")
    async def lizazombie(self, interaction: discord.Interaction):
        if is_active():
            await interaction.response.send_message("⚠️ A zombie game is already running.", ephemeral=True)
            return

        await interaction.response.send_message("🧟 Starting zombie survival game...", ephemeral=True)

        g = GameState(interaction.user.id)
        g.story_seed = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator."},
            {"role": "user", "content": "Generate a vivid, eerie zombie survival setting."}
        ])
        g.story_context = f"Setting: {g.story_seed}\n"
        globals()["active_game"] = g

        prompt = build_scene_prompt(g)
        raw_scene = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator."},
            {"role": "user", "content": prompt}
        ])
        bullets = [format_bullet(s.strip()) for s in re.split(r'(?<=[.!?])\s+', raw_scene) if s.strip()]
        await interaction.channel.send("━━━━━━━━━━━━━━\n🎭 **Scene 1**\n━━━━━━━━━━━━━━")
        await stream_bullets_in_message(interaction.channel, bullets, delay=2.5)

    @app_commands.command(name="endzombie", description="Manually end the zombie game")
    async def endzombie(self, interaction: discord.Interaction):
        if not is_active():
            await interaction.response.send_message("⚠️ No active zombie game to end.", ephemeral=True)
            return

        end_game()
        await interaction.response.send_message("🛑 Zombie game ended.", ephemeral=True)
        await interaction.channel.send("☠️ The survivors' story has come to a close.")

    @app_commands.command(name="zombiestatus", description="Show current survivors, deaths, and round number")
    async def zombiestatus(self, interaction: discord.Interaction):
        if not is_active():
            await interaction.response.send_message("⚠️ No active zombie game.", ephemeral=True)
            return

        g = active_game
        survivors = ", ".join(g.alive) if g.alive else "None"
        deaths = ", ".join(g.dead) if g.dead else "None"
        round_info = f"🧟 Round: {g.round_number}"

        summary = (
            f"🧍 Survivors: {survivors}\n"
            f"☠️ Deaths: {deaths}\n"
            f"{round_info}"
        )
        await interaction.response.send_message(summary, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    g = active_game
    if g and not g.terminated and g.options:
        content = message.content.strip()
        if content.isdigit():
            vote = int(content)
            if 1 <= vote <= len(g.options):
                g.votes[message.author.id] = vote
                await message.add_reaction("✅")

async def main():
    async with bot:
        await bot.load_extension("__main__")  # Assuming this file is run directly
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())

def merge_quotes_and_actions(bullets: list[str]) -> list[str]:
    merged = []
    buffer = ""
    for line in bullets:
        if line.startswith("•"):
            line = line[1:].strip()
        if '"' in line:
            if buffer:
                merged.append(format_bullet(buffer.strip()))
                buffer = ""
            merged.append(format_bullet(line.strip()))
        else:
            buffer += " " + line
    if buffer:
        merged.append(format_bullet(buffer.strip()))
    return merged

def parse_stats_from_narration(bullets: list[str], g: GameState):
    for line in bullets:
        lowered = line.lower()
        for name in g.alive:
            if name.lower() in lowered:
                if "helps" in lowered or "rescues" in lowered:
                    g.stats["helped"][name] += 1
                if "clever" in lowered or "resourceful" in lowered or "improvises" in lowered:
                    g.stats["resourceful"][name] += 1
                if "betrays" in lowered or "sacrifices" in lowered or "coldly" in lowered:
                    g.stats["sinister"][name] += 1
                if "honor" in lowered or "dignity" in lowered or "refuses to run" in lowered:
                    g.stats["dignified"][name] += 1

def track_relationships(bullets: list[str], g: GameState):
    for line in bullets:
        for name1 in g.alive:
            for name2 in g.alive:
                if name1 != name2 and name1 in line and name2 in line:
                    if any(kw in line.lower() for kw in ["protects", "comforts", "saves", "leans on"]):
                        g.stats["bonds"][(name1, name2)] += 1
                    if any(kw in line.lower() for kw in ["argues", "blames", "fights", "abandons"]):
                        g.stats["conflicts"][(name1, name2)] += 1

async def run_next_round(channel: discord.TextChannel):
    g = active_game
    if not g or g.terminated:
        await channel.send("⚠️ No active game.")
        return

    prompt = build_scene_prompt(g)
    raw_scene = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": prompt}
    ])
    if not raw_scene:
        await channel.send("⚠️ AI failed to generate scene.")
        return

    bullets = enforce_bullets(raw_scene)
    bullets = merge_quotes_and_actions(bullets)
    bullets = [bold_character_names(b) for b in bullets]

    await channel.send(f"━━━━━━━━━━━━━━\n🎭 **Scene {g.round_number}**\n━━━━━━━━━━━━━━")
    await stream_bullets_in_message(channel, bullets, delay=2.5)

    parse_stats_from_narration(bullets, g)
    track_relationships(bullets, g)

    # Generate voting options
    vote_prompt = (
        f"Setting: {g.story_seed}\n"
        f"Alive: {', '.join(g.alive)}\n"
        "Generate 3 numbered choices for what the survivors should do next. "
        "Make them tense, morally ambiguous, and character-driven."
    )
    raw_options = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": vote_prompt}
    ])
    if not raw_options:
        await channel.send("⚠️ AI failed to generate voting options.")
        return

    option_lines = [line.strip() for line in raw_options.splitlines() if re.match(r"^\d+\.", line.strip())]
    g.options = [re.sub(r"^\d+\.\s*", "", line) for line in option_lines if line]

    if not g.options:
        await channel.send("⚠️ No valid options parsed. Using fallback.")
        g.options = ["Run for the forest", "Barricade the school", "Search the basement"]

    selected = await collect_votes(channel, g.options, timeout=30)
    g.last_choice = g.options[selected - 1]

    # Generate outcome
    outcome_prompt = (
        f"Setting: {g.story_seed}\n"
        f"Alive: {', '.join(g.alive)}\n"
        f"Choice: {g.last_choice}\n"
        "Describe what happens next. Include tension, consequences, and character reactions. "
        "End with a clear 'Deaths:' and 'Survivors:' line."
    )
    outcome_text = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": outcome_prompt}
    ])
    if not outcome_text:
        await channel.send("⚠️ AI failed to generate outcome.")
        return

    await finalize_round(channel, outcome_text)

@app_commands.command(name="nextzombieround", description="Manually trigger the next round")
async def nextzombieround(self, interaction: discord.Interaction):
    if not is_active():
        await interaction.response.send_message("⚠️ No active zombie game.", ephemeral=True)
        return
    await interaction.response.send_message("🔁 Advancing to next round...", ephemeral=True)
    await run_next_round(interaction.channel)

@app_commands.command(name="zombiedebug", description="Show raw game state for debugging")
async def zombiedebug(self, interaction: discord.Interaction):
    if not is_active():
        await interaction.response.send_message("⚠️ No active zombie game.", ephemeral=True)
        return
    g = active_game
    debug_text = (
        f"🧠 Initiator: <@{g.initiator}>\n"
        f"🧍 Alive: {', '.join(g.alive)}\n"
        f"☠️ Dead: {', '.join(g.dead)}\n"
        f"🔁 Round: {g.round_number}\n"
        f"📜 Last Choice: {g.last_choice}\n"
        f"🗳️ Options: {g.options}\n"
        f"📊 Votes: {g.votes}\n"
        f"📈 Stats: {dict(g.stats)}"
    )
    await interaction.response.send_message(debug_text, ephemeral=True)

@app_commands.command(name="testscene", description="Generate a test scene with current survivors")
async def testscene(self, interaction: discord.Interaction):
    if not is_active():
        await interaction.response.send_message("⚠️ No active zombie game.", ephemeral=True)
        return
    g = active_game
    prompt = build_scene_prompt(g)
    raw_scene = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": prompt}
    ])
    if not raw_scene:
        await interaction.response.send_message("⚠️ AI failed to generate scene.", ephemeral=True)
        return
    bullets = enforce_bullets(raw_scene)
    bullets = merge_quotes_and_actions(bullets)
    bullets = [bold_character_names(b) for b in bullets]
    await interaction.channel.send("━━━━━━━━━━━━━━\n🧪 **Test Scene**\n━━━━━━━━━━━━━━")
    await stream_bullets_in_message(interaction.channel, bullets, delay=2.0)

def is_malformed_response(text: str) -> bool:
    if not text:
        return True
    if "Deaths:" not in text or "Survivors:" not in text:
        return True
    if len(text.strip().splitlines()) < 3:
        return True
    return False

async def safe_generate_scene(prompt: str, retries: int = 3) -> str:
    for attempt in range(retries):
        result = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator."},
            {"role": "user", "content": prompt}
        ])
        if result and not is_malformed_response(result):
            return result
        logger.warning(f"⚠️ Malformed AI response on attempt {attempt + 1}")
    return "Deaths: None\nSurvivors: Everyone\n• The scene was skipped due to a corrupted response."

async def safe_generate_options(prompt: str, fallback: list[str]) -> list[str]:
    result = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": prompt}
    ])
    if not result:
        return fallback
    option_lines = [line.strip() for line in result.splitlines() if re.match(r"^\d+\.", line.strip())]
    parsed = [re.sub(r"^\d+\.\s*", "", line) for line in option_lines if line]
    return parsed if parsed else fallback

def log_game_state(g: GameState):
    logger.info(f"🧠 GameState Dump — Round {g.round_number}")
    logger.info(f"Alive: {g.alive}")
    logger.info(f"Dead: {g.dead}")
    logger.info(f"Last Choice: {g.last_choice}")
    logger.info(f"Options: {g.options}")
    logger.info(f"Votes: {g.votes}")
    logger.info(f"Stats: {dict(g.stats)}")

async def advance_story_with_choice(channel: discord.TextChannel):
    g = active_game
    if not g or g.terminated:
        await channel.send("⚠️ No active game.")
        return

    prompt = (
        f"{g.story_context}\n"
        f"Alive: {', '.join(g.alive)}\n"
        f"Choice: {g.last_choice}\n"
        "Continue the story. Focus on consequences, character reactions, and eerie atmosphere. "
        "End with 'Deaths:' and 'Survivors:' lines."
    )
    raw_scene = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": prompt}
    ])
    if not raw_scene:
        await channel.send("⚠️ AI failed to generate continuation.")
        return

    g.story_context += f"\nRound {g.round_number}: {g.last_choice}\n{raw_scene}\n"
    await finalize_round(channel, raw_scene)

def get_stream_delay(g: GameState) -> float:
    # You originally tuned this based on round number or survivor count
    if g.round_number <= 2:
        return 2.5
    elif len(g.alive) <= 4:
        return 3.5
    else:
        return 2.0

async def stream_scene_with_context(channel: discord.TextChannel, bullets: list[str]):
    g = active_game
    delay = get_stream_delay(g)
    if not bullets:
        await channel.send("⚠️ No scene content to stream.")
        return

    msg = await channel.send("...")
    content = ""
    for bullet in bullets:
        content += bullet + "\n\n"
        await msg.edit(content=content.strip())
        await asyncio.sleep(delay)

def clean_and_merge_bullets(raw_text: str) -> list[str]:
    lines = raw_text.strip().splitlines()
    merged = []
    buffer = ""

    for line in lines:
        line = line.strip().lstrip("•").strip()
        if not line:
            continue

        if '"' in line:
            if buffer:
                merged.append(format_bullet(buffer.strip()))
                buffer = ""
            merged.append(format_bullet(line))
        else:
            buffer += " " + line

    if buffer:
        merged.append(format_bullet(buffer.strip()))

    # Remove duplicates
    seen = set()
    final = []
    for bullet in merged:
        if bullet not in seen:
            final.append(bullet)
            seen.add(bullet)

    return [bold_character_names(b) for b in final]

def process_ai_narration(raw_text: str) -> list[str]:
    # Enforce bullet formatting, merge quotes, bold names
    bullets = enforce_bullets(raw_text)
    merged = merge_quotes_and_actions(bullets)
    cleaned = [bold_character_names(b) for b in merged]
    return cleaned

async def deliver_narration(channel: discord.TextChannel, raw_text: str):
    bullets = process_ai_narration(raw_text)
    if not bullets:
        await channel.send("⚠️ Narration was empty or malformed.")
        return
    await stream_bullets_in_message(channel, bullets, delay=2.5)

async def execute_round(channel: discord.TextChannel):
    g = active_game
    if not g or g.terminated:
        await channel.send("⚠️ No active game.")
        return

    # Generate scene
    scene_prompt = build_scene_prompt(g)
    raw_scene = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": scene_prompt}
    ])
    if not raw_scene:
        await channel.send("⚠️ AI failed to generate scene.")
        return

    narration_bullets = process_ai_narration(raw_scene)
    await channel.send(f"━━━━━━━━━━━━━━\n🎭 **Scene {g.round_number}**\n━━━━━━━━━━━━━━")
    await stream_bullets_in_message(channel, narration_bullets, delay=get_stream_delay(g))

    # Generate voting options
    vote_prompt = build_voting_prompt(g)
    raw_options = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": vote_prompt}
    ])
    if not raw_options:
        await channel.send("⚠️ AI failed to generate voting options.")
        return

    option_lines = [line.strip() for line in raw_options.splitlines() if re.match(r"^\d+\.", line.strip())]
    g.options = [re.sub(r"^\d+\.\s*", "", line) for line in option_lines if line]

    await channel.send("━━━━━━━━━━━━━━\n🗳️ **Vote Now**\n━━━━━━━━━━━━━━")
    selected = await collect_votes(channel, g.options, timeout=30)
    g.last_choice = g.options[selected - 1]

    # Generate outcome
    outcome_prompt = build_outcome_prompt(g)
    raw_outcome = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": outcome_prompt}
    ])
    if not raw_outcome:
        await channel.send("⚠️ AI failed to generate outcome.")
        return

    await finalize_round(channel, raw_outcome)

async def game_loop(channel: discord.TextChannel):
    g = active_game
    if not g or g.terminated:
        await channel.send("⚠️ No active game.")
        return

    while g.alive and not g.terminated:
        await execute_round(channel)
        await asyncio.sleep(5)  # brief pause between rounds

    if not g.alive:
        await channel.send("☠️ All survivors have perished. The story ends here.")
        await end_summary(channel)
        end_game()

@app_commands.command(name="startzombiegame", description="Start the zombie game and begin the loop")
async def startzombiegame(self, interaction: discord.Interaction):
    if is_active():
        await interaction.response.send_message("⚠️ A zombie game is already running.", ephemeral=True)
        return

    await interaction.response.send_message("🧟 Initializing zombie survival game...", ephemeral=True)

    g = GameState(interaction.user.id)
    g.story_seed = await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator."},
        {"role": "user", "content": "Generate a vivid, eerie zombie survival setting."}
    ])
    g.story_context = f"Setting: {g.story_seed}\n"
    globals()["active_game"] = g

    await interaction.channel.send("━━━━━━━━━━━━━━\n🎭 **Opening Scene**\n━━━━━━━━━━━━━━")
    await game_loop(interaction.channel)

@app_commands.command(name="shutdownzombie", description="Forcefully shut down the zombie game")
async def shutdownzombie(self, interaction: discord.Interaction):
    global active_game
    if not is_active():
        await interaction.response.send_message("⚠️ No active zombie game.", ephemeral=True)
        return

    active_game.terminated = True
    await interaction.response.send_message("🛑 Zombie game forcefully shut down.", ephemeral=True)
    await interaction.channel.send("☠️ The game has been terminated prematurely.")

def restart_game():
    global active_game
    active_game = None
