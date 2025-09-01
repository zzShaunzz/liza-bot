import discord
from discord.ext import commands
import os
import logging
import asyncio

# 🔒 Load secrets from environment variables
RULES_MESSAGE_ID = int(os.environ.get("RULES_MESSAGE_ID", 0))
RULES_CHANNEL_ID = int(os.environ.get("RULES_CHANNEL_ID", 0))
VERIFIED_ROLE_ID = int(os.environ.get("VERIFIED_ROLE_ID", 0))
OWNER_ID = int(os.environ.get("OWNER_ID", 0))  # Optional: restrict !auditverify to owner
BUILD_TAG = os.environ.get("BUILD_TAG", "dev")  # For !version command

class VerifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def backfill_verified_users(self):
        await self.bot.wait_until_ready()
        await self.audit_verified_roles()

    async def audit_verified_roles(self):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            logging.error("[VerifyCog] ❌ Guild not found.")
            return

        channel = guild.get_channel(RULES_CHANNEL_ID)
        role = guild.get_role(VERIFIED_ROLE_ID)

        if not channel or not role:
            logging.error("[VerifyCog] ❌ Channel or role not found.")
            return

        try:
            message = await channel.fetch_message(RULES_MESSAGE_ID)
        except Exception as e:
            logging.error(f"[VerifyCog] ❌ Failed to fetch rules message: {e}")
            return

        reacted_user_ids = set()
        for reaction in message.reactions:
            if str(reaction.emoji) == "✅":
                async for user in reaction.users():
                    reacted_user_ids.add(user.id)

        verified_added = 0
        verified_removed = 0

        async for member in guild.fetch_members(limit=None):
            if member.bot:
                continue

            has_role = role in member.roles
            reacted = member.id in reacted_user_ids

            try:
                if reacted and not has_role:
                    await member.add_roles(role)
                    verified_added += 1
                    logging.info(f"[VerifyCog] ✅ Added Verified role to {member.display_name}")
                elif not reacted and has_role:
                    await member.remove_roles(role)
                    verified_removed += 1
                    logging.info(f"[VerifyCog] ❌ Removed Verified role from {member.display_name} (no reaction)")
            except Exception as e:
                logging.warning(f"[VerifyCog] ⚠️ Role update failed for {member.display_name}: {e}")

        logging.info(f"[VerifyCog] 🔍 Audit complete: Verified {verified_added}, Removed {verified_removed}")

    @commands.command(name="auditverify")
    async def auditverify_command(self, ctx: commands.Context):
        if OWNER_ID and ctx.author.id != OWNER_ID:
            await ctx.send("🚫 You don't have permission to run this command.")
            return

        await ctx.send("🔍 Running verification audit...")
        await self.audit_verified_roles()
        await ctx.send("✅ Audit complete. Check console for details.")

    @commands.command(name="version")
    async def version_command(self, ctx: commands.Context):
        await ctx.send(f"🛠️ Bot version: `{BUILD_TAG}`")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if (
            payload.message_id != RULES_MESSAGE_ID or
            payload.channel_id != RULES_CHANNEL_ID or
            str(payload.emoji) != "✅"
        ):
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            return

        if member.bot:
            return

        role = guild.get_role(VERIFIED_ROLE_ID)
        if role and role not in member.roles:
            try:
                await member.add_roles(role)
                logging.info(f"[VerifyCog] ✅ Added Verified role to {member.display_name}")
            except Exception as e:
                logging.warning(f"[VerifyCog] ⚠️ Failed to add role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if (
            payload.message_id != RULES_MESSAGE_ID or
            payload.channel_id != RULES_CHANNEL_ID or
            str(payload.emoji) != "✅"
        ):
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            return

        if member.bot:
            return

        role = guild.get_role(VERIFIED_ROLE_ID)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
                logging.info(f"[VerifyCog] ❌ Removed Verified role from {member.display_name}")
            except Exception as e:
                logging.warning(f"[VerifyCog] ⚠️ Failed to remove role: {e}")

# ✅ Safe async setup function
async def setup(bot: commands.Bot):
    cog = VerifyCog(bot)
    await bot.add_cog(cog)
    try:
        asyncio.create_task(cog.backfill_verified_users())
        logging.info("[VerifyCog] 🔄 Scheduled backfill_verified_users task.")
        logging.info(f"[VerifyCog] 🛠️ Running bot version: {BUILD_TAG}")
    except Exception as e:
        logging.exception("[VerifyCog] ❌ Failed to schedule backfill task.")
