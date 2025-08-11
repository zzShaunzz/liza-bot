import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import json
import os
import pytz  # ✅ Added for timezone support

print("[BirthdayCog] birthday.py was imported.")

# Channel IDs
GENERAL_CHANNEL_ID = 1196335052662001744
BOT_CHANNEL_ID = 1399117366926770267

# Birthday data (display names mapped to MM-DD format)
BIRTHDAYS = {
    "Dylan Pastorin 🥸": "08-08",
    "Vivian Christine Muy ✡️": "01-27",
    "Noah James Nainggolan 🥩": "08-28",
    "Gabriel Dante Muy ♿": "07-16",
    "Addison Reese Sadsarin 👨🏿‍🌾": "10-01",
    "Jill Olivia Nainggolan 👺": "02-12",
    "Shaun Maxwell Sadsarin 🗿": "05-17",
    "Aiden Michael Muy 🤑": "05-12",
    "Kate August Nainggolan 🐒": "08-12",
    "Jordan 🛐": "04-11",
    "Nico Noah Muy 🐸": "01-08",
    "Ella Muy 💴": "06-22"
}

class BirthdayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_birthdays.start()
        print("[BirthdayCog] Loaded and birthday loop started.")

    def cog_unload(self):
        self.check_birthdays.cancel()

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=pytz.timezone("US/Pacific")))  # ✅ Runs daily at midnight PST
    async def check_birthdays(self):
        await self.bot.wait_until_ready()
        pst = pytz.timezone("US/Pacific")
        today = datetime.datetime.now(pst).date()
        tomorrow = today + datetime.timedelta(days=1)
        date_key = tomorrow.strftime("%Y-%m-%d")

        print(f"[BirthdayCog] Checking for birthdays on {date_key} (PST)...")

        announced = self.load_announced()

        for name, date_str in BIRTHDAYS.items():
            month, day = map(int, date_str.split("-"))
            if tomorrow.month == month and tomorrow.day == day:
                if date_key in announced and name in announced[date_key]:
                    print(f"[BirthdayCog] Already announced for {name} on {date_key}. Skipping.")
                    continue

                channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
                if channel:
                    await channel.send(f"{name}'s birthday is tomorrow... @🔔 general ping.")
                    print(f"[BirthdayCog] Birthday alert sent for: {name}")
                    announced.setdefault(date_key, []).append(name)
                    self.save_announced(announced)

    def load_announced(self):
        if not os.path.exists("announced_birthdays.json"):
            return {}
        with open("announced_birthdays.json", "r") as f:
            return json.load(f)

    def save_announced(self, data):
        with open("announced_birthdays.json", "w") as f:
            json.dump(data, f, indent=2)

    def get_closest_birthday(self):
        pst = pytz.timezone("US/Pacific")
        today = datetime.datetime.now(pst).date()
        soonest_name = None
        min_days = 366

        for name, date_str in BIRTHDAYS.items():
            month, day = map(int, date_str.split("-"))
            bday_this_year = datetime.date(today.year, month, day)

            if bday_this_year >= today:
                delta = (bday_this_year - today).days
            else:
                next_year_bday = datetime.date(today.year + 1, month, day)
                delta = (next_year_bday - today).days

            if delta < min_days:
                min_days = delta
                soonest_name = name

        return soonest_name, min_days

    def get_last_birthday(self):
        pst = pytz.timezone("US/Pacific")
        today = datetime.datetime.now(pst).date()
        latest_name = None
        min_days = 366

        for name, date_str in BIRTHDAYS.items():
            month, day = map(int, date_str.split("-"))
            bday_this_year = datetime.date(today.year, month, day)

            if bday_this_year < today:
                delta = (today - bday_this_year).days
            else:
                prev_year_bday = datetime.date(today.year - 1, month, day)
                delta = (today - prev_year_bday).days

            if delta < min_days:
                min_days = delta
                latest_name = name

        return latest_name, min_days

    @app_commands.command(name="closestbday", description="Find the next upcoming birthday")
    async def closestbday_slash(self, interaction: discord.Interaction):
        if interaction.channel.id != BOT_CHANNEL_ID:
            await interaction.response.send_message(
                "⛔ This command can only be used in the bot's channel.", ephemeral=True
            )
            return

        name, days = self.get_closest_birthday()
        if name:
            await interaction.response.send_message(
                f"🎉 The next birthday is **{name}** in {days} days!"
            )
        else:
            await interaction.response.send_message("No birthdays found.")

    @commands.command(name="closestbday")
    async def closestbday_prefix(self, ctx: commands.Context):
        if ctx.channel.id != BOT_CHANNEL_ID:
            await ctx.send("⛔ This command can only be used in the bot's channel.")
            return

        name, days = self.get_closest_birthday()
        if name:
            await ctx.send(f"🎉 The next birthday is **{name}** in {days} days!")
        else:
            await ctx.send("No birthdays found.")

    @app_commands.command(name="lastbday", description="Find the most recent birthday that passed")
    async def lastbday_slash(self, interaction: discord.Interaction):
        if interaction.channel.id != BOT_CHANNEL_ID:
            await interaction.response.send_message(
                "⛔ This command can only be used in the bot's channel.", ephemeral=True
            )
            return

        name, days = self.get_last_birthday()
        if name:
            await interaction.response.send_message(
                f"🎈 The most recent birthday was **{name}**, {days} days ago!"
            )
        else:
            await interaction.response.send_message("No birthdays found.")

    @commands.command(name="lastbday")
    async def lastbday_prefix(self, ctx: commands.Context):
        if ctx.channel.id != BOT_CHANNEL_ID:
            await ctx.send("⛔ This command can only be used in the bot's channel.")
            return

        name, days = self.get_last_birthday()
        if name:
            await ctx.send(f"🎈 The most recent birthday was **{name}**, {days} days ago!")
        else:
            await ctx.send("No birthdays found.")

# Required setup function for cog loading
async def setup(bot):
    await bot.add_cog(BirthdayCog(bot))
