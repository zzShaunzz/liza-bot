import os
import discord
from discord.ext import commands

OWNER_ID = int(os.getenv("OWNER_ID"))  # ← Loaded securely from Replit secrets

class MessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="lizasay")
    async def lizasay(self, ctx, *, message: str):
        if ctx.author.id != OWNER_ID:
            await ctx.send(
                "⛔ Sorry, only 4Deezus can use this command.",
                delete_after=3  # ✅ Auto-delete after 3 seconds
            )
            return

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            await ctx.send(
                "⚠️ I couldn't delete your message due to missing permissions."
            )

        await ctx.send(message)

async def setup(bot):
    await bot.add_cog(MessageCog(bot))