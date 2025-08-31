import discord, asyncio
from discord.ext import commands
from config import CHANNEL_ID
from game_state import start_game, end_game, is_active, active_game
from story_engine import generate_story
from utils import tally_votes, extract_options

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command(name="lizazombie")
async def lizazombie_text(ctx):
    if ctx.channel.id != CHANNEL_ID:
        return
    if is_active():
        await ctx.send("Game is currently in process.")
        return
    start_game(ctx.author.id)
    await ctx.send("🧟‍♂️ Zombie survival game started! Round 1 begins in 5 seconds...")
    await asyncio.sleep(5)
    await run_round(ctx)

@bot.event
async def on_ready():
    print(f"{bot.user} is online.")

async def run_round(ctx):
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
    await asyncio.sleep(3)

    if len(g.alive) <= 3:
        await ctx.send("⚠️ Only 3 survivors remain. Conflict intensifies...")
        # Add betrayal logic here
    elif len(g.alive) == 1:
        await ctx.send(f"🏆 {g.alive[0]} is the sole survivor!")
        # Add final stats here
        end_game()
        return

    await run_round(ctx)
