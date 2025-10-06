import discord
from discord.ext import commands
import random
import aiohttp
import os

class RandomPull(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="randompull", description="Pulls a random message from the server and provides AI-generated context.")
    async def random_pull(self, ctx):
        await ctx.defer()  # Defer response to avoid timeout

        # Fetch all text channels in the server
        channels = [channel for channel in ctx.guild.text_channels if channel.permissions_for(ctx.me).read_messages]

        if not channels:
            await ctx.send("No accessible text channels found in this server.")
            return

        # Select a random channel
        channel = random.choice(channels)

        try:
            # Fetch messages from the channel (limit to 100 for performance)
            messages = [msg async for msg in channel.history(limit=100)]
            if not messages:
                await ctx.send(f"No messages found in {channel.mention}.")
                return

            # Select a random message
            message = random.choice(messages)

            # Generate AI context using OpenRouter
            context = await self.generate_ai_context(message.content)

            # Create a jump URL
            jump_url = message.jump_url

            # Construct the response
            embed = discord.Embed(
                title="Random Message Pull",
                description=f"**Message:** {message.content}\n**Channel:** {channel.mention}\n**Author:** {message.author.mention}\n**Sent at:** {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                color=discord.Color.random()
            )
            embed.add_field(name="AI Context", value=context, inline=False)
            embed.add_field(name="Jump to Message", value=f"[Click here]({jump_url})", inline=False)

            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send(f"I don't have permission to read messages in {channel.mention}.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    async def generate_ai_context(self, message_content):
        """Generate a short AI context using OpenRouter API."""
        api_keys = [
            os.getenv("OPENROUTER_API_KEY_1"),
            os.getenv("OPENROUTER_API_KEY_2"),
            os.getenv("OPENROUTER_API_KEY_3"),
            os.getenv("OPENROUTER_API_KEY_4"),
            os.getenv("OPENROUTER_API_KEY_5"),
            os.getenv("OPENROUTER_API_KEY_6"),
        ]
        api_key = random.choice([key for key in api_keys if key])

        if not api_key:
            return "No AI context available (API key missing)."

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mistralai/mistral-7b-instruct",
            "messages": [
                {"role": "user", "content": f"Summarize the following message in 10 words or less: '{message_content}'"}
            ],
            "max_tokens": 10
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        return "Failed to generate context."
        except Exception:
            return "Failed to generate context."

async def setup(bot):
    await bot.add_cog(RandomPull(bot))
