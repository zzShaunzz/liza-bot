import discord

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
