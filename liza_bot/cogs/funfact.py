import discord
from discord.ext import commands
import aiohttp

class FunFactCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="funfact")
    async def funfact(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://uselessfacts.jsph.pl/random.json?language=en") as response:
                if response.status == 200:
                    data = await response.json()
                    fact = data.get("text", "Couldn't fetch a fun fact right now.")
                else:
                    fact = "Oops! The fun fact machine is taking a nap."

        await ctx.send(f"🧠 Fun Fact: {fact}")

async def setup(bot):
    await bot.add_cog(FunFactCog(bot))