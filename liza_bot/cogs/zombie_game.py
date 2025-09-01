import discord
from discord.ext import commands
from discord import app_commands
import os, random, json, asyncio, logging, requests
from dotenv import load_dotenv

# 🧠 Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔒 Load environment variables
load_dotenv()
ZOMBIE_CHANNEL_ID = int(os.getenv("ZOMBIE_CHANNEL_ID", "0"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL", "openrouter/mixtral")

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
            active_game.stats["bonds"][pair] = active_game.stats["bonds"].get(pair, 1) + 2
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
        "Write a vivid scene describing what each character is doing at the start of this round. "
        "Include emotional tension, physical actions, and hints of interpersonal dynamics. "
        "Do not describe any new threat or dilemma yet — just set the scene.\n"
    )

    return context

async def generate_intro_scene(retry=False):
    prompt = build_intro_context()
    messages = [
        {"role": "system", "content": "You are a horror storyteller narrating a zombie survival RPG."},
        {"role": "user", "content": prompt}
    ]

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

        logger.debug(f"[ZombieGame] 🧠 Intro prompt:\n{prompt}")
        logger.debug(f"[ZombieGame] 🧠 Raw response:\n{response.text}")
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if not content:
            if not retry:
                logger.warning("⚠️ Intro scene empty — retrying once...")
                return await generate_intro_scene(retry=True)
            logger.warning("⚠️ Fallback triggered. Intro scene was empty after retry.")
            return "The survivors gather in silence, each lost in thought as the night deepens."

        logger.info("[ZombieGame] ✅ Intro scene generated.")
        return content

    except Exception as e:
        logger.error(f"💥 Failed to generate intro scene: {e}")
        return "The survivors gather in silence, each lost in thought as the night deepens."

def build_dilemma_context():
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
        "Now describe a new zombie-related dilemma the group faces. "
        "Include emotional tension, character reactions, and two distinct options for the group to vote on. "
        "Format the options clearly as '1.' and '2.' at the end of the story.\n"
    )

    return context

async def generate_story(retry=False):
    prompt = build_dilemma_context()
    messages = [
        {"role": "system", "content": "You are a horror storyteller narrating a zombie survival RPG."},
        {"role": "user", "content": prompt}
    ]

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

        logger.debug(f"[ZombieGame] 🧠 Dilemma prompt:\n{prompt}")
        logger.debug(f"[ZombieGame] 🧠 Raw response:\n{response.text}")
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if not content:
            if not retry:
                logger.warning("⚠️ Dilemma empty — retrying once...")
                return await generate_story(retry=True)
            logger.warning("⚠️ Fallback triggered. Dilemma was empty after retry.")
            return "The group faces a mysterious threat, but the details are unclear."

        logger.info("[ZombieGame] ✅ Dilemma generated.")
        return content

    except Exception as e:
        logger.error(f"💥 Failed to generate dilemma: {e}")
        return "The group faces a mysterious threat, but the details are unclear."

async def tally_votes(message: discord.Message):
    votes = {"1️⃣": 0, "2️⃣": 0}
    for reaction in message.reactions:
        if reaction.emoji in votes:
            votes[reaction.emoji] = reaction.count - 1
    return votes

def extract_options(text: str):
    lines = text.split("\n")
    options = [line for line in lines if line.strip().startswith(("1.", "2."))]
    return options if len(options) == 2 else ["Option A", "Option B"]

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

class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def start_game_flow(self, channel: discord.TextChannel, user_id: int):
        if channel.id != ZOMBIE_CHANNEL_ID:
            await channel.send("❌ This command can only be run in the designated game channel.")
            return
        if is_active():
            await channel.send("⚠️ A zombie game is already in progress.")
            return
        start_game(user_id)
        await channel.send("🧟‍♀️ Zombie survival game started! Round 1 begins in 3 seconds...")
        await asyncio.sleep(3)
        await self.run_round(channel)

    @app_commands.command(name="lizazombie", description="Start the zombie survival RPG with Liza")
    async def lizazombie_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            await self.start_game_flow(interaction.channel, interaction.user.id)
        except Exception as e:
            await interaction.followup.send(f"💥 Error during game flow: `{e}`")

    @commands.command(name="lizazombie")
    async def lizazombie(self, ctx: commands.Context):
        try:
            await self.start_game_flow(ctx.channel, ctx.author.id)
        except Exception as e:
            await ctx.send(f"💥 Error during game flow: `{e}`")

    @commands.command(name="testintro")
async def test_intro(self, ctx: commands.Context):
    prompt = build_intro_context()
    response = await generate_intro_scene()
    await ctx.send(f"🧪 Prompt:\n```{prompt}```\n🧠 Response:\n{response}")

async def run_round(self, channel: discord.TextChannel):
    g = active_game
    g.round += 1

    # Phase 1: AI-generated intro scene
    logger.debug("[ZombieGame] 🧠 Generating intro scene...")
    intro = await generate_intro_scene()
    logger.debug(f"[ZombieGame] Intro scene content:\n{intro}")
    await channel.send(f"🎭 **Scene**\n{intro}")
    await asyncio.sleep(15)

    # Phase 2: AI-generated dilemma
    logger.debug("[ZombieGame] 🧠 Generating dilemma...")
    dilemma = await generate_story()
    logger.debug(f"[ZombieGame] Dilemma content:\n{dilemma}")
    g.options = extract_options(dilemma)
    await channel.send(f"🧠 **Dilemma**\n{dilemma}")

    vote_msg = await channel.send("Vote now! ⏳ 15 seconds...\nReact with 1️⃣ or 2️⃣")
    await vote_msg.add_reaction("1️⃣")
    await vote_msg.add_reaction("2️⃣")
    await asyncio.sleep(15)

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
    cog = ZombieGame(bot)
    await bot.add_cog(cog)
    print("✅ ZombieGame cog loaded")
