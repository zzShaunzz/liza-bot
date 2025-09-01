import discord
from discord.ext import commands
from discord import app_commands
import os, random, asyncio, logging, aiohttp
from dotenv import load_dotenv
from collections import defaultdict

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
ZOMBIE_CHANNEL_ID = int(os.getenv("ZOMBIE_CHANNEL_ID", "0"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL")

# Utility to bold names in Discord messages
def bold_name(name: str) -> str:
    return f"**{name}**"

def bold_character_names(text: str) -> str:
    for name in CHARACTER_INFO.keys():
        text = text.replace(name, bold_name(name))
    return text

def enforce_bullets(text: str) -> str:
    lines = text.split("\n")
    return "\n".join([f"• {line.strip()}" if line.strip() and not line.startswith("•") else line for line in lines])

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
        "traits": ["strong", "peacekeeper", "withdraws under pressure", "hand-to-hand expert"],
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
        self.terminated = False

active_game = None

def end_game():
    global active_game
    if active_game:
        active_game.terminated = True

def is_active():
    return active_game is not None and not active_game.terminated

# AI generation
async def generate_ai_text(messages, temperature=0.9):
    if active_game and active_game.terminated:
        return None

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature
    }

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
                        return content
                    logger.warning("AI response was empty.")
        except Exception as e:
            logger.error(f"AI request error: {type(e).__name__} - {e}")
        await asyncio.sleep(2 ** attempt)

    logger.error("AI request failed after 3 attempts.")
    return None

# Prompt builders
async def generate_unique_setting():
    messages = [
        {"role": "system", "content": "You are a horror storyteller."},
        {"role": "user", "content": "🎬 Generate a unique setting for a zombie survival story. Be vivid, eerie, and specific. Avoid generic locations. Describe the environment in one sentence."}
    ]
    return await generate_ai_text(messages)

def build_scene_prompt():
    g = active_game
    traits = "\n".join([f"{bold_name(name)}: {', '.join(CHARACTER_INFO[name]['traits'])}" for name in g.alive])
    return (
        f"🧠 Setting: {g.story_seed}\n"
        f"🧍 Alive characters: {', '.join([bold_name(name) for name in g.alive])}\n"
        f"🧠 Traits:\n{traits}\n\n"
        "🎬 Write a vivid zombie survival scene. Include every character. Format each character’s action as a bullet point. Use paragraph breaks between groups. Keep each line concise."
    )

def build_scene_summary_prompt(scene_text):
    return f"🧠 Based on the scene below, summarize the key events in no more than 3 sentences.\n\n{scene_text}"

def build_health_prompt():
    g = active_game
    return (
        f"🧍 Alive characters: {', '.join([bold_name(name) for name in g.alive])}\n\n"
        "🧠 Describe each character's physical condition (healthy, sick, injured, etc.) in one sentence each. Format each description as a bullet point. Then summarize the group's emotional state, trust level, and any rising bonds or conflicts."
    )

def build_dilemma_prompt():
    return "🧠 Based on the scene and health report above, describe the new problem that arises. Limit the dilemma to 2 sentences. Do not include any choices yet."

def build_choices_prompt():
    return "🧠 Based on the dilemma above, generate two distinct choices the group must vote on. Format each as a numbered option. Keep them short and dramatic."

# AI generators
async def generate_scene():
    messages = [
        {"role": "system", "content": "You are a horror storyteller narrating a zombie survival RPG."},
        {"role": "user", "content": build_scene_prompt()}
    ]
    return await generate_ai_text(messages)

async def generate_scene_summary(scene_text):
    messages = [
        {"role": "system", "content": "You are a horror narrator summarizing a zombie survival scene."},
        {"role": "user", "content": build_scene_summary_prompt(scene_text)}
    ]
    return await generate_ai_text(messages, temperature=0.7)

async def generate_health_report():
    messages = [
        {"role": "system", "content": "You are a horror narrator tracking character wellbeing and group dynamics."},
        {"role": "user", "content": build_health_prompt()}
    ]
    return await generate_ai_text(messages)

async def generate_dilemma():
    messages = [
        {"role": "system", "content": "You are a horror storyteller narrating a zombie survival RPG."},
        {"role": "user", "content": build_dilemma_prompt()}
    ]
    return await generate_ai_text(messages, temperature=0.7)

async def generate_choices():
    messages = [
        {"role": "system", "content": "You are a horror storyteller narrating a zombie survival RPG."},
        {"role": "user", "content": build_choices_prompt()}
    ]
    return await generate_ai_text(messages, temperature=0.8)

# Streaming functions
async def stream_text_wordwise(message: discord.Message, full_text: str, delay: float = 0.03, chunk_size: int = 4):
    if not full_text:
        await message.edit(content="⚠️ Failed to generate text.")
        return

    words = full_text.split()
    output = ""
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size])
        output += chunk + " "
        if len(output) > 1900:
            await message.edit(content=output.strip())
            output = ""
            await asyncio.sleep(delay * 10)
        else:
            await message.edit(content=output.strip())
            await asyncio.sleep(delay)

    if output:
        await message.edit(content=output.strip())

async def chunk_and_stream(channel: discord.TextChannel, full_text: str, delay: float = 0.03):
    chunks = []
    current = ""
    for line in full_text.split("\n"):
        if len(current) + len(line) + 1 > 1900:
            chunks.append(current.strip())
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current.strip())

    for chunk in chunks:
        msg = await channel.send("...")
        await stream_text_wordwise(msg, chunk, delay=delay)

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

    @commands.command(name="endgame")
    async def endgame_legacy(self, ctx: commands.Context):
        if not is_active():
            await ctx.send("⚠️ No active game to end.")
            return
        end_game()
        await ctx.send("🧟‍♀️ Zombie game manually ended.")

    @app_commands.command(name="endgame", description="Manually end the current zombie game")
    async def endgame_slash(self, interaction: discord.Interaction):
        if not is_active():
            await interaction.response.send_message("⚠️ No active game to end.", ephemeral=True)
            return
        end_game()
        await interaction.response.send_message("🧟‍♀️ Zombie game manually ended.")

    async def run_round(self, channel: discord.TextChannel):
        g = active_game
        g.round += 1

        if g.terminated:
            await channel.send("🛑 Game has been terminated.")
            return

        # Phase 1: Scene generation
        raw_scene = await generate_scene()
        if g.terminated or not raw_scene:
            await channel.send("🛑 Game terminated or scene generation failed.")
            return
        scene_text = enforce_bullets(bold_character_names(raw_scene))
        scene_msg = await channel.send("...")
        await stream_text_wordwise(scene_msg, f"🎭 **Scene**\n{scene_text}", delay=0.03)
        await asyncio.sleep(2)

        # Phase 2: Scene summary
        raw_summary = await generate_scene_summary(scene_text)
        if raw_summary:
            summary_text = bold_character_names(raw_summary)
            summary_msg = await channel.send("...")
            await stream_text_wordwise(summary_msg, f"📝 **Scene Summary**\n{summary_text}", delay=0.03)
        await asyncio.sleep(2)

        # Phase 3: Health report
        raw_health = await generate_health_report()
        if g.terminated or not raw_health:
            await channel.send("🛑 Game terminated or health report failed.")
            return
        health_text = bold_character_names(raw_health)
        await chunk_and_stream(channel, f"🩺 **Health & Relationships**\n{health_text}", delay=0.03)
        await asyncio.sleep(2)

        # Phase 4: Dilemma generation
        raw_dilemma = await generate_dilemma()
        if g.terminated or not raw_dilemma:
            await channel.send("🛑 Game terminated or dilemma generation failed.")
            return
        dilemma_text = bold_character_names(raw_dilemma)
        dilemma_msg = await channel.send("...")
        await stream_text_wordwise(dilemma_msg, f"🧠 **Dilemma**\n{dilemma_text}", delay=0.03)
        await asyncio.sleep(2)

        # Phase 5: Choice generation
        raw_choices = await generate_choices()
        if g.terminated or not raw_choices:
            await channel.send("🛑 Game terminated or choice generation failed.")
            return

        g.options = [line.strip() for line in raw_choices.split("\n") if line.strip().startswith(("1.", "2."))]
        if len(g.options) != 2:
            await channel.send("⚠️ AI did not return two valid choices. Ending game.")
            end_game()
            return

        choices_msg = await channel.send("...")
        await stream_text_wordwise(choices_msg, "🔀 **Choices**\n" + "\n".join(g.options), delay=0.03)
        await choices_msg.add_reaction("1️⃣")
        await choices_msg.add_reaction("2️⃣")
        await asyncio.sleep(10)

        countdown_msg = await channel.send("⏳ Voting ends in...")
        await countdown_message(countdown_msg, 15, "⏳ Voting ends in...")

        if g.terminated:
            await channel.send("🛑 Game terminated during voting.")
            return

        choices_msg = await channel.fetch_message(choices_msg.id)
        votes = await tally_votes(choices_msg)

        if votes["1️⃣"] == 0 and votes["2️⃣"] == 0:
            await channel.send("No votes cast. Game over.")
            end_game()
            return

        choice = g.options[0] if votes["1️⃣"] >= votes["2️⃣"] else g.options[1]
        g.last_choice = choice

        # Phase 6: Outcome narration
        outcome_prompt = (
            f"The group chose: {choice}\n"
            f"Alive characters: {', '.join([bold_name(name) for name in g.alive])}\n"
            "🧠 Describe how this choice led to either group benefits or character deaths. "
            "Be vivid but concise. Then list the deaths and survivors in bullet format."
        )
        messages = [
            {"role": "system", "content": "You are a horror narrator describing consequences of group decisions."},
            {"role": "user", "content": outcome_prompt}
        ]
        raw_outcome = await generate_ai_text(messages, temperature=0.8)
        outcome_text = bold_character_names(raw_outcome or "⚠️ Outcome generation failed. Proceeding with random deaths.")

        deaths = random.sample(g.alive, k=random.randint(0, min(4, len(g.alive))))
        for name in deaths:
            g.alive.remove(name)
            g.dead.insert(0, name)

        survivors = g.alive.copy()
        death_lines = "\n".join([f"• {bold_name(name)}" for name in deaths]) or "• None"
        survivor_lines = "\n".join([f"• {bold_name(name)}" for name in survivors]) or "• None"

        g.last_events = (
            f"🧾 **Outcome**\n{outcome_text}\n\n"
            f"💀 **Deaths This Round**\n{death_lines}\n\n"
            f"🧍 **Remaining Survivors**\n{survivor_lines}"
        )
        await chunk_and_stream(channel, g.last_events, delay=0.03)
        update_stats(g)
        await asyncio.sleep(10)

        # End condition check
        if len(g.alive) <= random.randint(1, 5):
            if len(g.alive) == 1:
                await channel.send(f"🏆 {bold_name(g.alive[0])} is the sole survivor!")
            else:
                await channel.send(f"🏁 Final survivors:\n" + "\n".join([f"• {bold_name(name)}" for name in g.alive]))
            await self.end_summary(channel)
            end_game()
            return

        await self.run_round(channel)

    async def end_summary(self, channel: discord.TextChannel):
        g = active_game
        await channel.send("📜 **Game Summary**")
        await channel.send("🪦 Deaths (most recent first):\n" + "\n".join([f"• {bold_name(name)}" for name in g.dead]))

        await channel.send("📊 **Final Stats**")
        await channel.send(f"🏅 Most helpful: {get_top_stat(g.stats['helpful'])}")
        await channel.send(f"😈 Most sinister: {get_top_stat(g.stats['sinister'])}")
        await channel.send(f"🔧 Most resourceful: {get_top_stat(g.stats['resourceful'])}")

        bonds = sorted(g.stats["bonds"].items(), key=lambda x: x[1], reverse=True)
        conflicts = sorted(g.stats["conflicts"].items(), key=lambda x: x[1], reverse=True)

        if bonds:
            await channel.send(f"🤝 Greatest bond: {bold_name(bonds[0][0][0])} & {bold_name(bonds[0][0][1])} ({bonds[0][1]} points)")
        if conflicts:
            await channel.send(f"⚔️ Biggest opps: {bold_name(conflicts[0][0][0])} vs {bold_name(conflicts[0][0][1])} ({conflicts[0][1]} points)")

        await channel.send(f"🕊️ Most dignified: {get_top_stat(g.stats['dignified'])}")

        recap_prompt = (
            f"🧠 Final recap request:\n"
            f"Characters who died: {', '.join([bold_name(name) for name in g.dead])}\n"
            f"Final survivors: {', '.join([bold_name(name) for name in g.alive])}\n"
            f"Key choices made: {g.last_choice}\n"
            f"Strongest bond: {bold_name(bonds[0][0][0])} & {bold_name(bonds[0][0][1])}\n"
            f"Biggest conflict: {bold_name(conflicts[0][0][0])} vs {bold_name(conflicts[0][0][1])}\n\n"
            "🎬 Write a brief cinematic summary of the entire game. Include how characters died, what relationships changed, and any major emotional or strategic turning points. Keep it under 200 words."
        )
        messages = [
            {"role": "system", "content": "You are a horror narrator summarizing a zombie survival story."},
            {"role": "user", "content": recap_prompt}
        ]
        raw_recap = await generate_ai_text(messages, temperature=0.8)
        recap_text = bold_character_names(raw_recap or "⚠️ Final recap generation failed.")
        await chunk_and_stream(channel, "🎞️ **Final Recap**\n" + recap_text, delay=0.03)

        await channel.send("🎬 Thanks for surviving (or not) the zombie apocalypse. Until next time...")

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    print("✅ ZombieGame cog loaded")
