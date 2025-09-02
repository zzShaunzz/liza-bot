import discord
from discord.ext import commands
from discord import app_commands
import os, asyncio, logging, aiohttp, re
from dotenv import load_dotenv
from collections import defaultdict

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env vars
load_dotenv()
ZOMBIE_CHANNEL_ID = int(os.getenv("ZOMBIE_CHANNEL_ID", "0"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL")

# ---------- Formatting ----------
def bold_name(name: str) -> str:
    return f"**{name}**"

def bold_character_names(text: str) -> str:
    name_parts = set()
    for full_name in CHARACTER_INFO.keys():
        name_parts.add(full_name)
        for part in full_name.split():
            name_parts.add(part)
    sorted_names = sorted(name_parts, key=len, reverse=True)
    for name in sorted_names:
        # Match "Name" or "Name's" and bold the entire match
        pattern = re.compile(rf"(?<!\*)\b({re.escape(name)}(?:'s)?)\b(?!\*)", re.IGNORECASE)
        text = pattern.sub(lambda m: f"**{m.group(1)}**", text)
    return text

def enforce_bullets(text: str) -> list:
    """Convert AI text into a list of clean bullet lines with spacing."""
    matches = re.findall(r"(?:•|\*)\s*(.+?)(?=(?:\s*(?:•|\*)|$))", text, re.DOTALL)
    bullets = []
    if matches:
        for line in matches:
            clean = line.strip().strip('*').strip('•')
            if clean:
                bullets.append(f"• {clean}")
    else:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        bullets = [f"• {s.strip()}" for s in sentences if s.strip()]
    # Add spacing between bullets
    spaced = []
    for b in bullets:
        spaced.append(b)
        spaced.append("")  # blank line between bullets
    return spaced

async def send_bullets_one_by_one(channel: discord.TextChannel, bullets: list, delay: float = 0.8):
    for bullet in bullets:
        if bullet.strip():  # Only send non-empty lines
            await channel.send(bullet)
            await asyncio.sleep(delay)

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

# ---------- Characters ----------
CHARACTER_INFO = {
    "Shaun Sadsarin": {
        "age": 15, "gender": "Male",
        "traits": ["organizer", "strong", "fast", "heat-sensitive", "pattern-adapter"],
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
        "traits": ["mentally brave", "protective", "strong with tools", "slow mover", "manipulation-prone", "extroverted"],
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
        "likely_conflicts": ["Aiden Muy"]
    },
    "Kate Nainggolan": {
        "age": 14, "gender": "Female",
        "traits": ["manipulative", "quick-witted", "enduring", "persuasive"],
        "siblings": ["Jill Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Dylan Pastorin", "Gabe Muy", "Addison Sadsarin", "Shaun Sadsarin"],
        "likely_conflicts": ["Nico Muy"]
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
        "traits": ["strong", "peacekeeper", "withdraws under pressure", "hand-to-hand expert"],
        "siblings": ["Vivian Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Aiden Muy", "Nico Muy", "Shaun Sadsarin", "Noah Nainggolan"],
        "likely_conflicts": ["Shaun Sadsarin"]
    },
    "Aiden Muy": {
        "age": 14, "gender": "Male",
        "traits": ["agile", "crafty", "chef", "mental reader"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Shaun Sadsarin", "Jordan", "Nico Muy", "Addison Sadsarin"],
        "likely_conflicts": ["Addison Sadsarin"]
    },
    "Ella Muy": {
        "age": 11, "gender": "Female",
        "traits": ["physically reliant", "luckiest"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Nico Muy"],
        "likely_pairs": ["Addison Sadsarin", "Jill Nainggolan", "Kate Nainggolan", "Vivian Muy"],
        "likely_conflicts": ["Nico Muy"]
    },
    "Nico Muy": {
        "age": 12, "gender": "Male",
        "traits": ["daring", "comical", "risk-taker", "needs guidance"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Ella Muy"],
        "likely_pairs": ["Jordan", "Aiden Muy", "Gabe Muy", "Shaun Sadsarin"],
        "likely_conflicts": ["Ella Muy"]
    },
    "Jordan": {
        "age": 13, "gender": "Male",
        "traits": ["gentle", "quietly skilled", "stronger than he seems"],
        "siblings": [],
        "likely_pairs": ["Nico Muy", "Gabe Muy", "Aiden Muy", "Dylan Pastorin"],
        "likely_conflicts": ["Noah Nainggolan"]
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
            "helpful": {name: 0 for name in CHARACTERS},
            "sinister": {name: 0 for name in CHARACTERS},
            "resourceful": {name: 0 for name in CHARACTERS},
            "bonds": defaultdict(int),
            "conflicts": defaultdict(int),
            "dignified": {name: 100 for name in CHARACTERS}
        }
        self.story_seed = None
        self.story_context = ""  # NEW: accumulates narrative for continuity
        self.terminated = False

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
    payload = {"model": MODEL, "messages": messages, "temperature": temperature}
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=45)
                ) as response:
                    if response.status != 200:
                        logger.error(f"AI request failed with status {response.status}: {await response.text()}")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    data = await response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if content:
                        logger.info(f"AI returned:\n{content}")
                        return content
                    logger.warning("AI response was empty.")
        except Exception as e:
            logger.error(f"AI request error: {type(e).__name__} - {e}")
        await asyncio.sleep(2 ** attempt)
    logger.error("AI request failed after 3 attempts.")
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
    traits = "\n".join([f"{bold_name(n)}: {', '.join(CHARACTER_INFO[n]['traits'])}" for n in g.alive])
    return (
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join([bold_name(n) for n in g.alive])}\n"
        f"🧠 Traits:\n{traits}\n\n"
        "🎬 Continue the story. Include every alive character. "
        "Format each action as a bullet point using •. Keep bullets short and on their own lines."
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
        "Format each as a bullet point using •."
    )

def build_group_dynamics_prompt():
    g = active_game
    return (
        f"{g.story_context}\n"
        f"🧍 Alive: {', '.join(g.alive)}\n\n"
        "🧠 Describe the group's emotional state, bonds, and conflicts in bullet points using •."
    )

def build_dilemma_prompt(scene_text, health_text):
    return (
        f"{active_game.story_context}\n"
        f"Scene:\n{scene_text}\n\n"
        f"Health:\n{health_text}\n\n"
        "🧠 Describe a new problem that arises, specific to this situation. "
        "Format as exactly two bullet points using •."
    )

def build_choices_prompt(dilemma_text):
    return (
        f"{active_game.story_context}\n"
        f"Dilemma:\n{dilemma_text}\n\n"
        "🧠 Provide exactly two distinct choices the group must vote on. "
        "Format each as a numbered bullet starting with '1.' and '2.'."
    )

# ---------- AI Generators ----------

async def generate_scene():
    return await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating cinematic zombie survival scenes."},
        {"role": "user", "content": build_scene_prompt()}
    ])

async def generate_scene_summary(scene_text):
    return await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator summarizing a zombie survival scene."},
        {"role": "user", "content": build_scene_summary_prompt(scene_text)}
    ], temperature=0.7)

async def generate_health_report():
    return await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating a health report."},
        {"role": "user", "content": build_health_prompt()}
    ])

async def generate_group_dynamics():
    return await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator describing group dynamics."},
        {"role": "user", "content": build_group_dynamics_prompt()}
    ])

async def generate_dilemma(scene_text, health_text):
    return await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating dilemmas for a survival game."},
        {"role": "user", "content": build_dilemma_prompt(scene_text, health_text)}
    ], temperature=0.9)

async def generate_choices(dilemma_text):
    return await generate_ai_text([
        {"role": "system", "content": "You are a horror narrator generating voting choices."},
        {"role": "user", "content": build_choices_prompt(dilemma_text)}
    ], temperature=0.8)

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
        await msg.edit(content="🧟‍♀️ Game started!")
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
        await msg.edit(content="🧟‍♀️ Game started!")
        await self.run_round(interaction.channel)

    async def run_round(self, channel: discord.TextChannel):
        g = active_game
        g.round += 1

        if g.terminated:
            await channel.send("🛑 Game has been terminated.")
            return

        # Phase 1: Scene
        raw_scene = await generate_scene()
        if not raw_scene:
            await channel.send("⚠️ Scene generation failed.")
            return
        scene_bullets = enforce_bullets(bold_character_names(raw_scene))
        await channel.send("━━━━━━━━━━━━━━\n🎭 **Scene**")
        await send_bullets_one_by_one(channel, scene_bullets)
        g.story_context += "\n".join(scene_bullets) + "\n"

        # Phase 2: Summary
        raw_summary = await generate_scene_summary("\n".join(scene_bullets))
        if raw_summary:
            await channel.send("━━━━━━━━━━━━━━\n📝 **Scene Summary**")
            await channel.send(bold_character_names(raw_summary.strip()))
            g.story_context += f"Summary: {raw_summary.strip()}\n"

        # Phase 3: Health
        raw_health = await generate_health_report()
        if not raw_health:
            await channel.send("⚠️ Health report failed.")
            return
        health_bullets = enforce_bullets(bold_character_names(raw_health))
        await channel.send("━━━━━━━━━━━━━━\n🩺 **Health Status**")
        await send_bullets_one_by_one(channel, health_bullets)

        # Phase 3b: Group Dynamics
        raw_dynamics = await generate_group_dynamics()
        if raw_dynamics:
            dynamics_bullets = enforce_bullets(bold_character_names(raw_dynamics))
            await channel.send("💬 **Group Dynamics**")
            await send_bullets_one_by_one(channel, dynamics_bullets)

        # Phase 4: Dilemma
        raw_dilemma = await generate_dilemma("\n".join(scene_bullets), "\n".join(health_bullets))
        if not raw_dilemma:
            await channel.send("⚠️ Dilemma generation failed.")
            return
        dilemma_bullets = enforce_bullets(bold_character_names(raw_dilemma))
        await channel.send("━━━━━━━━━━━━━━\n🧠 **Dilemma**")
        await send_bullets_one_by_one(channel, dilemma_bullets)

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
        await send_bullets_one_by_one(channel, g.options)

        # Voting
        choices_msg = await channel.send("🗳️ React to vote!")
        await choices_msg.add_reaction("1️⃣")
        await choices_msg.add_reaction("2️⃣")
        countdown_msg = await channel.send("⏳ Voting ends in...")
        await countdown_message(countdown_msg, 15, "⏳ Voting ends in...")
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

        # Update game state
        g.dead.extend([re.sub(r"^\W+", "", b).strip("*• ").strip() for b in deaths_list if b])
        g.alive = [re.sub(r"^\W+", "", b).strip("*• ").strip() for b in survivors_list if b]

        # Send outcome narration
        await channel.send("━━━━━━━━━━━━━━\n🧾 **Outcome**")
        narration_only = re.split(r"Deaths:", raw_outcome, flags=re.IGNORECASE)[0].strip()
        await channel.send(bold_character_names(narration_only))
        g.story_context += narration_only + "\n"

        # Send deaths and survivors
        await channel.send("💀 **Deaths This Round**")
        await send_bullets_one_by_one(channel, deaths_list)
        await channel.send("🧍 **Remaining Survivors**")
        await send_bullets_one_by_one(channel, survivors_list)

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
        await self.run_round(channel)

    async def end_summary(self, channel: discord.TextChannel):
        g = active_game
        await channel.send("━━━━━━━━━━━━━━\n📜 **Game Summary**")

        deaths_block = [f"• {bold_name(name)}" for name in g.dead] or ["• None"]
        await channel.send("🪦 **Deaths (most recent first)**")
        await send_bullets_one_by_one(channel, deaths_block)

        await channel.send("━━━━━━━━━━━━━━\n📊 **Final Stats**")
        await channel.send(f"🏅 Most helpful:\n• {get_top_stat(g.stats['helpful'])}")
        await channel.send(f"😈 Most sinister:\n• {get_top_stat(g.stats['sinister'])}")
        await channel.send(f"🔧 Most resourceful:\n• {get_top_stat(g.stats['resourceful'])}")

        bonds = sorted(g.stats["bonds"].items(), key=lambda x: x[1], reverse=True)
        conflicts = sorted(g.stats["conflicts"].items(), key=lambda x: x[1], reverse=True)
        bond_pair = bonds[0][0] if bonds else ("None", "None")
        conflict_pair = conflicts[0][0] if conflicts else ("None", "None")

        await channel.send(f"🤝 Greatest bond:\n• {bold_name(bond_pair[0])} & {bold_name(bond_pair[1])}")
        await channel.send(f"⚔️ Biggest opps:\n• {bold_name(conflict_pair[0])} vs {bold_name(conflict_pair[1])}")
        await channel.send(f"🕊️ Most dignified:\n• {get_top_stat(g.stats['dignified'])}")

        recap_prompt = (
            f"{g.story_context}\n"
            f"Deaths: {', '.join(g.dead)}\n"
            f"Survivors: {', '.join(g.alive)}\n"
            f"Key choices made: {g.last_choice}\n"
            f"Strongest bond: {bond_pair[0]} & {bond_pair[1]}\n"
            f"Biggest conflict: {conflict_pair[0]} vs {conflict_pair[1]}\n\n"
            "🎬 Write a brief cinematic recap of the entire game in bullet points."
        )
        raw_recap = await generate_ai_text([
            {"role": "system", "content": "You are a horror narrator summarizing a zombie survival story."},
            {"role": "user", "content": recap_prompt}
        ], temperature=0.85)
        recap_bullets = enforce_bullets(bold_character_names(raw_recap or "⚠️ Recap generation failed."))
        await channel.send("━━━━━━━━━━━━━━\n🎞️ **Final Recap**")
        await send_bullets_one_by_one(channel, recap_bullets)
        await channel.send("🎬 Thanks for surviving (or not) the zombie apocalypse. Until next time...")

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    print("✅ ZombieGame cog loaded")

# Utilities
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

