import discord, asyncio, os, requests, random
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
ZOMBIE_CHANNEL_ID = int(os.getenv("ZOMBIE_CHANNEL_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL", "openrouter/mixtral")

CHARACTERS = [
    "Shaun Sadsarin", "Addison Sadsarin", "Kate Nainggolan", "Jill Nainggolan", "Noah Nainggolan",
    "Dylan Pastorin", "Gabe Muy", "Vivian Muy", "Aiden Muy", "Ella Muy", "Nico Muy", "Jordan"
]

class GameState:
    def __init__(self, initiator):
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
            "bonds": {},       # (name1, name2): score
            "conflicts": {},   # (name1, name2): score
            "dignified": {name: 100 for name in CHARACTERS}
        }

active_game = None

def start_game(user_id):
    global active_game
    active_game = GameState(user_id)

def end_game():
    global active_game
    active_game = None

def is_active():
    return active_game is not None

def build_prompt():
    g = active_game
    prompt = f"Round {g.round}\n"
    if g.round > 1:
        prompt += f"Last round recap: {g.last_events}\n"
    prompt += f"Alive characters: {', '.join(g.alive)}\n"
    prompt += "Describe a new zombie-related problem the group faces. Include character insights, emerging tensions, and two options to vote on.\n"
    return prompt

async def generate_story():
    messages = [
        {"role": "system", "content": "You are a horror storyteller narrating a zombie survival RPG."},
        {"role": "user", "content": build_prompt()}
    ]
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "messages": messages,
            "temperature": 0.8
        }
    )
    return response.json()["choices"][0]["message"]["content"]

async def tally_votes(message):
    votes = {"1️⃣": 0, "2️⃣": 0}
    for reaction in message.reactions:
        if reaction.emoji in votes:
            votes[reaction.emoji] = reaction.count - 1
    return votes

def extract_options(text):
    lines = text.split("\n")
    options = [line for line in lines if line.strip().startswith(("1.", "2."))]
    return options if len(options) == 2 else ["Option A", "Option B"]

def update_stats(g: GameState):
    # Simulate stat changes per round
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

def get_top_stat(stat_dict):
    if not stat_dict:
        return "None"
    top = max(stat_dict.items(), key=lambda x: x[1])
    return f"{top[0]} ({top[1]} points)"

class ZombieGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="lizazombie")
    async def lizazombie_text(self, ctx):
        if ctx.channel.id != ZOMBIE_CHANNEL_ID:
            await ctx.send("❌ This command can only be run in the designated game channel.")
            return
        if is_active():
            await ctx.send("Game is currently in process.")
            return
        start_game(ctx.author.id)
        await ctx.send("🧟‍♂️ Zombie survival game started! Round 1 begins in 5 seconds...")
        await asyncio.sleep(5)
        await self.run_round(ctx)

    async def run_round(self, ctx):
        g = active_game
        g.round += 1

        story = await generate_story()
        g.options = extract_options(story)

        await ctx.send(f"**Round {g.round}**\n{story}")
        vote_msg = await ctx.send("Vote now! ⏳ 30 seconds...\nReact with 1️⃣ or 2️⃣")
        await vote_msg.add_reaction("1️⃣")
        await vote_msg.add_reaction("2️⃣")

        await asyncio.sleep(30)
        votes = await tally_votes(vote_msg)

        if votes["1️⃣"] == 0 and votes["2️⃣"] == 0:
            await ctx.send("No votes cast. Game over.")
            end_game()
            return

        choice = g.options[0] if votes["1️⃣"] >= votes["2️⃣"] else g.options[1]
        g.last_choice = choice
        g.last_events = f"The group chose: {choice}"

        await ctx.send(f"Majority chose: **{choice}**")
        update_stats(g)
        await asyncio.sleep(3)

        deaths = random.sample(g.alive, k=random.randint(0, min(4, len(g.alive))))
        for name in deaths:
            g.alive.remove(name)
            g.dead.insert(0, name)
        if deaths:
            await ctx.send(f"💀 The following characters died: {', '.join(deaths)}")

        if len(g.alive) <= 3:
            await ctx.send("⚠️ Only 3 survivors remain. Conflict intensifies...")
        elif len(g.alive) == 1:
            await ctx.send(f"🏆 {g.alive[0]} is the sole survivor!")
            await self.end_summary(ctx)
            end_game()
            return

        await self.run_round(ctx)

    async def end_summary(self, ctx):
        g = active_game
        await ctx.send("📜 **Game Summary**")
        await ctx.send("🪦 Deaths (most recent first):\n" + "\n".join([f"• {name}" for name in g.dead]))

        await ctx.send("📊 **Final Stats**")
        await ctx.send(f"🏅 Most helpful: {get_top_stat(g.stats['helpful'])}")
        await ctx.send(f"😈 Most sinister: {get_top_stat(g.stats['sinister'])}")
        await ctx.send(f"🔧 Most resourceful: {get_top_stat(g.stats['resourceful'])}")

        bonds = sorted(g.stats["bonds"].items(), key=lambda x: x[1], reverse=True)
        conflicts = sorted(g.stats["conflicts"].items(), key=lambda x: x[1], reverse=True)

        if bonds:
            await ctx.send(f"🤝 Greatest bond: {bonds[0][0][0]} & {bonds[0][0][1]} ({bonds[0][1]} points)")
        if conflicts:
            await ctx.send(f"⚔️ Biggest opps: {conflicts[0][0][0]} vs {conflicts[0][0][1]} ({conflicts[0][1]} points)")

        await ctx.send(f"🕊️ Most dignified: {get_top_stat(g.stats['dignified'])}")

async def setup(bot):
    await bot.add_cog(ZombieGame(bot))
