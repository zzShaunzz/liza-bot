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

CHARACTER_INFO = {
    "Shaun Sadsarin": {
        "age": 15, "gender": "Male",
        "traits": ["organizer", "strong", "fast", "heat-sensitive", "pattern-adapter"],
        "siblings": ["Addison Sadsarin"]
    },
    "Addison Sadsarin": {
        "age": 16, "gender": "Female",
        "traits": ["kind", "patient", "versatile", "physically weak", "slow decision-maker"],
        "siblings": ["Shaun Sadsarin"]
    },
    "Dylan Pastorin": {
        "age": 21, "gender": "Male",
        "traits": ["mentally brave", "protective", "strong with tools", "slow mover", "manipulation-prone", "extroverted"],
        "siblings": []
    },
    "Noah Nainggolan": {
        "age": 18, "gender": "Male",
        "traits": ["physically capable", "fighter", "not a planner"],
        "siblings": ["Kate Nainggolan", "Jill Nainggolan"]
    },
    "Jill Nainggolan": {
        "age": 16, "gender": "Female",
        "traits": ["conniving", "lucky", "swimmer"],
        "siblings": ["Kate Nainggolan", "Noah Nainggolan"]
    },
    "Kate Nainggolan": {
        "age": 14, "gender": "Female",
        "traits": ["manipulative", "quick-witted", "enduring", "persuasive"],
        "siblings": ["Jill Nainggolan", "Noah Nainggolan"]
    },
    "Vivian Muy": {
        "age": 18, "gender": "Female",
        "traits": ["wise", "calm", "insightful", "secret genius"],
        "siblings": ["Gabe Muy", "Aiden Muy", "Ella Muy", "Nico Muy"]
    },
    "Gabe Muy": {
        "age": 17, "gender": "Male",
        "traits": ["strong", "peacekeeper", "withdraws under pressure", "hand-to-hand expert"],
        "siblings": ["Vivian Muy", "Aiden Muy", "Ella Muy", "Nico Muy"]
    },
    "Aiden Muy": {
        "age": 14, "gender": "Male",
        "traits": ["agile", "crafty", "chef", "mental reader"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Ella Muy", "Nico Muy"]
    },
    "Ella Muy": {
        "age": 11, "gender": "Female",
        "traits": ["physically reliant", "luckiest"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Nico Muy"]
    },
    "Nico Muy": {
        "age": 12, "gender": "Male",
        "traits": ["daring", "comical", "risk-taker", "needs guidance"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Ella Muy"]
    },
    "Jordan": {
        "age": 13, "gender": "Male",
        "traits": ["gentle", "quietly skilled", "stronger than he seems"],
        "siblings": []
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

async def generate_ai_text(messages, temperature=0.9):
    if active_game and active_game.terminated:
        return None

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    logger.error(f"AI request failed with status {response.status}: {await response.text()}")
                    return None
                data = await response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except aiohttp.ClientError as e:
        logger.error(f"AI request failed: {type(e).__name__} - {e}")
    except asyncio.TimeoutError:
        logger.error("AI request timed out.")
    except Exception as e:
        logger.error(f"Unexpected error during AI request: {type(e).__name__} - {e}")
    return None

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                data = await response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error(f"AI request failed: {e}")
        return None

async def generate_unique_setting():
    prompt = (
        "🎬 Generate a unique setting for a zombie survival story. "
        "It should be vivid, eerie, and specific. Avoid generic locations. "
        "Describe the environment in one sentence."
    )
    messages = [
        {"role": "system", "content": "You are a horror storyteller."},
        {"role": "user", "content": prompt}
    ]
    return await generate_ai_text(messages)

async def start_game_async(user_id: int):
    global active_game
    active_game = GameState(user_id)
    active_game.story_seed = await generate_unique_setting()

def build_scene_prompt():
    g = active_game
    traits = "\n".join(
        [f"{name}: {', '.join(CHARACTER_INFO[name]['traits'])}" for name in g.alive]
    )
    return (
        f"🧠 Setting: {g.story_seed}\n"
        f"🧍 Alive characters: {', '.join(g.alive)}\n"
        f"🧠 Traits:\n{traits}\n\n"
        "🎬 Write a vivid zombie survival scene. Describe what each character is doing. "
        "Use bullet points and paragraph breaks. Do not introduce a new threat yet."
    )

def build_dilemma_prompt():
    return (
        "🧠 Based on the scene above, describe the new problem that arises. "
        "Limit the dilemma to 2 sentences. Do not include any choices yet."
    )

def build_choices_prompt():
    return (
        "🧠 Based on the dilemma above, generate two distinct choices the group must vote on. "
        "Format each as a numbered option. Keep them short and dramatic."
    )

async def generate_scene():
    messages = [
        {"role": "system", "content": "You are a horror storyteller narrating a zombie survival RPG."},
        {"role": "user", "content": build_scene_prompt()}
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

async def stream_text(message: discord.Message, full_text: str, delay: float = 0.8):
    if not full_text:
        await message.edit(content="⚠️ Failed to generate text.")
        return

    paragraphs = [line.strip() for line in full_text.split("\n") if line.strip()]
    bullets = [f"• {para}" for para in paragraphs]

    output = ""
    for bullet in bullets:
        if active_game and active_game.terminated:
            return
        output += bullet + "\n"
        if len(output) > 1900:
            output += "\n⚠️ Scene truncated due to Discord message limit."
            break
        try:
            await message.edit(content=output.strip())
            await asyncio.sleep(delay)
        except Exception as e:
            logger.warning(f"⚠️ Failed to stream bullet: {e}")
            break

async def countdown_message(message: discord.Message, seconds: int, prefix: str = ""):
    for i in range(seconds, 0, -1):
        if active_game and active_game.terminated:
            return
        try:
            await message.edit(content=f"{prefix} {i}")
            await asyncio.sleep(1)
        except:
            break

async def tally_votes(message: discord.Message):
    votes = {"1️⃣": 0, "2️⃣": 0}
    for reaction in message.reactions:
        if reaction.emoji in votes:
            votes[reaction.emoji] = reaction.count - 1
    return votes

def get_top_stat(stat_dict: dict):
    if not stat_dict:
        return "None"
    top = max(stat_dict.items(), key=lambda x: x[1])
    return f"{top[0]} ({top[1]} points)"

def update_stats(g: GameState):
    for name in random.sample(g.alive, k=random.randint(2, 5)):
        g.stats["helpful"][name] += random.randint(1, 3)
    for name in random.sample(g.alive, k=random.randint(1, 3)):
        g.stats["sinister"][name] += random.randint(1, 2)
    for name in random.sample(g.alive, k=random.randint(2, 4)):
        g.stats["resourceful"][name] += random.randint(1, 3)
    pairs = random.sample(g.alive, k=min(4, len(g.alive)))
    for i in range(0, len(pairs)-1, 2):
        pair = tuple(sorted((pairs[i], pairs[i+1])))
        g.stats["bonds"][pair] += random.randint(1, 3)
    if len(g.alive) > 3:
        conflict_pair = tuple(sorted(random.sample(g.alive, 2)))
        g.stats["conflicts"][conflict_pair] += random.randint(1, 2)
    for name in g.alive:
        g.stats["dignified"][name] -= random.randint(0, 2)

class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="lizazombie")
    async def lizazombie_legacy(self, ctx: commands.Context):
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
        await interaction.response.defer()
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
        loading_msg = await channel.send("🧠 Generating scene...")
        scene_text = await generate_scene()
        if g.terminated or not scene_text:
            await channel.send("🛑 Game terminated or scene generation failed.")
            return

        await stream_text(loading_msg, f"🎭 **Scene**\n{scene_text}", delay=0.8)
        await asyncio.sleep(10)

        # Phase 2: Dilemma generation
        dilemma_msg = await channel.send("🧠 Generating dilemma...")
        dilemma_text = await generate_dilemma()
        if g.terminated or not dilemma_text:
            await channel.send("🛑 Game terminated or dilemma generation failed.")
            return
        await dilemma_msg.edit(content=f"🧠 **Dilemma**\n{dilemma_text}")
        await asyncio.sleep(2)

        # Phase 3: Choice generation
        choices_text = await generate_choices()
        if g.terminated or not choices_text:
            await channel.send("🛑 Game terminated or choice generation failed.")
            return

        g.options = [line.strip() for line in choices_text.split("\n") if line.strip().startswith(("1.", "2."))]
        if len(g.options) != 2:
            await channel.send("⚠️ AI did not return two valid choices. Ending game.")
            end_game()
            return

        choices_msg = await channel.send("🔀 **Choices**\n" + "\n".join(g.options))
        await choices_msg.add_reaction("1️⃣")
        await choices_msg.add_reaction("2️⃣")

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

        deaths = random.sample(g.alive, k=random.randint(0, min(4, len(g.alive))))
        for name in deaths:
            g.alive.remove(name)
            g.dead.insert(0, name)

        g.last_events = f"🧾 Outcome: The group chose: **{choice}**.\n💀 Deaths: {', '.join(deaths) if deaths else 'None'}."

        await channel.send(g.last_events)
        update_stats(g)
        await asyncio.sleep(3)

        if len(g.alive) <= random.randint(1, 5):
            if len(g.alive) == 1:
                await channel.send(f"🏆 {g.alive[0]} is the sole survivor!")
            else:
                await channel.send(f"🏁 Final survivors: {', '.join(g.alive)}")
            await self.end_summary(channel)
            end_game()
            return

        await self.run_round(channel)

    async def end_summary(self, channel: discord.TextChannel):
        g = active_game
        await channel.send("📜 **Game Summary**")
        await channel.send("🪦 Deaths (most recent first):\n" + "\n".join([f"• {name}" for name in g.dead]))

        await channel.send("📊 **Final Stats**")
        await channel.send(f"🏅 Most helpful: {get_top_stat(g.stats['helpful'])}")
        await channel.send(f"😈 Most sinister: {get_top_stat(g.stats['sinister'])}")
        await channel.send(f"🔧 Most resourceful: {get_top_stat(g.stats['resourceful'])}")

        bonds = sorted(g.stats["bonds"].items(), key=lambda x: x[1], reverse=True)
        conflicts = sorted(g.stats["conflicts"].items(), key=lambda x: x[1], reverse=True)

        if bonds:
            await channel.send(f"🤝 Greatest bond: {bonds[0][0][0]} & {bonds[0][0][1]} ({bonds[0][1]} points)")
        if conflicts:
            await channel.send(f"⚔️ Biggest opps: {conflicts[0][0][0]} vs {conflicts[0][0][1]} ({conflicts[0][1]} points)")

        await channel.send(f"🕊️ Most dignified: {get_top_stat(g.stats['dignified'])}")
        await channel.send("🎬 Thanks for surviving (or not) the zombie apocalypse. Until next time...")

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    print("✅ ZombieGame cog loaded")
