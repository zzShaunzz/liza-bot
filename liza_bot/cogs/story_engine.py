import requests
from config import OPENROUTER_API_KEY, MODEL
from game_state import active_game

def build_prompt():
    g = active_game
    prompt = f"Round {g.round}\n"
    if g.round > 1:
        prompt += f"Last round recap: {g.last_events}\n"

    prompt += f"Alive characters: {', '.join(g.alive)}\n"
    prompt += f"Resources: {g.resources}\n"
    prompt += f"Health: {g.health}\n"
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

    content = response.json()["choices"][0]["message"]["content"]
    return content
