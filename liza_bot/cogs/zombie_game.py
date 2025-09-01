import discord
from discord.ext import commands
from discord import app_commands
import os, random, asyncio, logging, requests
from dotenv import load_dotenv

# 🧠 Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔒 Load environment variables
load_dotenv()
ZOMBIE_CHANNEL_ID = int(os.getenv("ZOMBIE_CHANNEL_ID", "0"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL", "openrouter/solar-10.7b-instruct")

if not OPENROUTER_API_KEY:
    logger.error("❌ OPENROUTER_API_KEY is missing.")
    raise SystemExit(1)

# 🎭 Character definitions
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
        "siblings": [],
        "likely_pairs": ["Gabe Muy", "Jill Nainggolan", "Kate Nainggolan", "Dylan Pastorin"],
        "likely_conflicts": ["Jill Nainggolan"]
    },
    "Jill Nainggolan": {
        "age": 16, "gender": "Female",
        "traits": ["conniving", "lucky", "swimmer"],
        "siblings": ["Kate Nainggolan", "Nico Muy"],
        "likely_pairs": ["Kate Nainggolan", "Noah Nainggolan", "Addison Sadsarin", "Gabe Muy"],
        "likely_conflicts": ["Aiden Muy"]
    },
    "Kate Nainggolan": {
        "age": 14, "gender": "Female",
        "traits": ["manipulative", "quick-witted", "enduring", "persuasive"],
        "siblings": ["Jill Nainggolan", "Nico Muy"],
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
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Ella Muy", "Jill Nainggolan", "Kate Nainggolan"],
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
            "bonds": {},
            "conflicts": {},
            "dignified": {name: 100 for name in CHARACTERS}
        }

active_game = None

def start_game(user_id: int):
    global active_game
    active_game = GameState(user_id)

    for i in range(len(CHARACTERS)):
        for j in range(i + 1, len(CHARACTERS)):
            pair = tuple(sorted((CHARACTERS[i], CHARACTERS[j])))
            active_game.stats["bonds"][pair] = 1

    for name, info in CHARACTER_INFO.items():
        for partner in info.get("likely_pairs", []):
            pair = tuple(sorted((name, partner)))
            active_game.stats["bonds"][pair] += 2
        for rival in info.get("likely_conflicts", []):
            pair = tuple(sorted((name, rival)))
            active_game.stats["conflicts"][pair] = active_game.stats["conflicts"].get(pair, 0) + 2

def end_game():
    global active_game
    active_game = None

def is_active():
    return active_game is not None

def build_intro_context():
    g = active_game
    context = f"Round {g.round}\n"

    if g.round > 1:
        context += f"Last round recap: {g.last_events}\n"

    context += f"Alive characters: {', '.join(g.alive)}\n"

    traits_summary = "\n".join(
        [f"{name}: {', '.join(CHARACTER_INFO[name]['traits'])}" for name in g.alive]
    )
    context += f"\nCharacter traits:\n{traits_summary}\n"

    context += (
        "Write a vivid, immersive scene of at least 100 words. "
        "Describe what each character is doing at the start of this round. "
        "Include emotional tension, physical actions, and interpersonal dynamics. "
        "Do not summarize. Do not skip details. Do not describe any new threat or dilemma yet — just set the scene.\n"
    )

    return context

def build_dilemma_context():
    g = active_game
    context = f"Round {g.round} dilemma:\n"

    context += (
        "Introduce a new threat or challenge that forces the group to make a difficult decision. "
        "Include environmental hazards, emotional stakes, and conflicting goals. "
        "Present two distinct options for how the group might respond. "
        "Label them clearly as '1.' and '2.' and make both options morally complex. "
        "Make the dilemma vivid and at least 100 words long.\n"
    )

    context += f"Alive characters: {', '.join(g.alive)}\n"

    return context

async def generate_intro_scene():
    prompt = build_intro_context()
    messages = [
        {"role": "system", "content": "You are a horror storyteller narrating a zombie survival RPG."},
        {"role": "user", "content": prompt}
    ]

    logger.debug(f"🧟 Prompt sent to model:\n{prompt}")

    for attempt in range(3):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                    "temperature": 0.9
                }
            )

            logger.debug(f"🧟 Full response JSON:\n{response.text}")
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            logger.debug(f"🧟 Raw intro output (attempt {attempt + 1}):\n{content}")

            if content:
                logger.info("[ZombieGame] ✅ Intro scene generated.")
                return content

            logger.warning(f"⚠️ Intro scene too short on attempt {attempt + 1}")
            await asyncio.sleep(2 ** attempt)

        except Exception as e:
            logger.error(f"💥 Intro generation error on attempt {attempt + 1}: {e}")
            await asyncio.sleep(2 ** attempt)

    raise RuntimeError("Intro scene generation failed after 3 attempts.")

async def generate_story():
    prompt = build_dilemma_context()
    messages = [
        {"role": "system", "content": "You are a horror storyteller narrating a zombie survival RPG."},
        {"role": "user", "content": prompt}
    ]

    logger.debug(f"🧟 Prompt sent to model:\n{prompt}")

    for attempt in range(3):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                    "temperature": 0.85
                }
            )

            logger.debug(f"🧟 Full response JSON:\n{response.text}")
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            logger.debug(f"🧟 Raw dilemma output (attempt {attempt + 1}):\n{content}")

            if content:
                logger.info("[ZombieGame] ✅ Dilemma generated.")
                return content

            logger.warning(f"⚠️ Dilemma too short on attempt {attempt + 1}")
            await asyncio.sleep(2 ** attempt)

        except Exception as e:
            logger.error(f"💥 Dilemma generation error on attempt {attempt + 1}: {e}")
            await asyncio.sleep(2 ** attempt)

    raise RuntimeError("Dilemma generation failed after 3 attempts.")

def extract_options(text: str):
    lines = text.split("\n")
    options = [line for line in lines if line.strip().startswith(("1.", "2."))]
    return options if len(options) == 2 else ["Option A", "Option B"]

async def tally_votes(message: discord.Message):
    votes = {"1️⃣": 0, "2️⃣": 0}
    for reaction in message.reactions:
        if reaction.emoji in votes:
            votes[reaction.emoji] = reaction.count - 1
    return votes

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
        g.stats["bonds"][pair] = g.stats["bonds"].get(pair, 0) + random.randint(1, 3)
    if len(g.alive) > 3:
        conflict_pair = tuple(sorted(random.sample(g.alive, 2)))
        g.stats["conflicts"][conflict_pair] = g.stats["conflicts"].get(conflict_pair, 0) + random.randint(1, 2)
    for name in g.alive:
        g.stats["dignified"][name] -= random.randint(0, 2)

def get_top_stat(stat_dict: dict):
    if not stat_dict:
        return "None"
    top = max(stat_dict.items(), key=lambda x: x[1])
    return f"{top[0]} ({top[1]} points)"

async def countdown_message(message: discord.Message, seconds: int, prefix: str = ""):
    for i in range(seconds, 0, -1):
        try:
            await message.edit(content=f"{prefix} {i}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"⚠️ Countdown edit failed: {e}")
            break

async def stream_text(message: discord.Message, full_text: str, chunk_size: int = 6, delay: float = 0.5):
    words = full_text.split()
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    output = ""
    for chunk in chunks:
        output += chunk + " "
        try:
            await message.edit(content=output.strip())
            await asyncio.sleep(delay)
        except Exception as e:
            logger.warning(f"⚠️ Failed to stream text: {e}")
            break

class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="lizazombie")
    async def lizazombie_legacy(self, ctx: commands.Context):
        if is_active():
            await ctx.send("⚠️ A zombie game is already running.")
            return
        start_game(ctx.author.id)
        msg = await ctx.send("🧟‍♀️ Zombie survival game starting in...")
        await countdown_message(msg, 3, "🧟‍♀️ Zombie survival game starting in...")
        await msg.edit(content="🧟‍♀️ Game started!")
        await self.run_round(ctx.channel)

    @app_commands.command(name="lizazombie", description="Start a zombie survival game")
    async def lizazombie_slash(self, interaction: discord.Interaction):
        if interaction.channel.id != ZOMBIE_CHANNEL_ID:
            await interaction.response.send_message("❌ Run this command in the zombie channel.", ephemeral=True)
            return
        if is_active():
            await interaction.response.send_message("⚠️ A zombie game is already running.", ephemeral=True)
            return
        start_game(interaction.user.id)
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

    @commands.command(name="testintro")
    async def test_intro(self, ctx: commands.Context):
        prompt = build_intro_context()
        await ctx.send(f"🧪 Prompt:\n```{prompt}```")
        response = await generate_intro_scene()
        await ctx.send(f"🧠 Response:\n{response}")

    @commands.command(name="testdilemma")
    async def test_dilemma(self, ctx: commands.Context):
        prompt = build_dilemma_context()
        await ctx.send(f"🧪 Prompt:\n```{prompt}```")
        response = await generate_story()
        await ctx.send(f"🧠 Response:\n{response}")

    async def run_round(self, channel: discord.TextChannel):
        g = active_game
        g.round += 1

        # Phase 1: Intro scene
        try:
            intro_text = await generate_intro_scene()
        except RuntimeError as e:
            logger.error(f"🧟 Intro scene failed: {e}")
            await channel.send("⚠️ Failed to generate the intro scene. The game cannot continue.")
            end_game()
            return

        intro_msg = await channel.send("🎭 Loading scene...")
        await stream_text(intro_msg, f"🎭 **Scene**\n{intro_text}", chunk_size=6, delay=0.6)
        await asyncio.sleep(15)

        # Phase 2: Dilemma
        try:
            dilemma_text = await generate_story()
        except RuntimeError as e:
            logger.error(f"🧟 Dilemma generation failed: {e}")
            await channel.send("⚠️ Failed to generate the dilemma. The game cannot continue.")
            end_game()
            return

        g.options = extract_options(dilemma_text)
        dilemma_msg = await channel.send("🧠 Loading dilemma...")
        await stream_text(dilemma_msg, f"🧠 **Dilemma**\n{dilemma_text}", chunk_size=6, delay=0.6)

        vote_msg = await channel.send("Vote now! ⏳\nReact with 1️⃣ or 2️⃣")
        await vote_msg.add_reaction("1️⃣")
        await vote_msg.add_reaction("2️⃣")
        await countdown_message(vote_msg, 15, "⏳ Voting ends in...")

        vote_msg = await channel.fetch_message(vote_msg.id)
        votes = await tally_votes(vote_msg)

        if votes["1️⃣"] == 0 and votes["2️⃣"] == 0:
            await channel.send("No votes cast. Game over.")
            end_game()
            return

        choice = g.options[0] if votes["1️⃣"] >= votes["2️⃣"] else g.options[1]
        g.last_choice = choice
        g.last_events = f"The group chose: {choice}"

        await channel.send(f"Majority chose: **{choice}**")
        update_stats(g)
        await asyncio.sleep(3)

        deaths = random.sample(g.alive, k=random.randint(0, min(4, len(g.alive))))
        for name in deaths:
            g.alive.remove(name)
            g.dead.insert(0, name)
        if deaths:
            await channel.send(f"💀 The following characters died: {', '.join(deaths)}")

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

# 🔧 Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    print("✅ ZombieGame cog loaded")
