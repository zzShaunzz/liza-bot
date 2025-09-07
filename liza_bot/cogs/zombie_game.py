import os
import re
import json
import asyncio
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import httpx
import discord
from discord.ext import commands
from discord import app_commands

# ────────────────────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zombie_game")

# ────────────────────────────────────────────────────────────
# Environment / Config
# ────────────────────────────────────────────────────────────
ZOMBIE_CHANNEL_ID = int(os.getenv("ZOMBIE_CHANNEL_ID", "0"))
MODEL = os.getenv("MODEL", "openai/gpt-4o-mini")

# 7 OpenRouter keys (includes the 7th slot)
OPENROUTER_API_KEYS = [
    os.getenv("OPENROUTER_API_KEY_1"),
    os.getenv("OPENROUTER_API_KEY_2"),
    os.getenv("OPENROUTER_API_KEY_3"),
    os.getenv("OPENROUTER_API_KEY_4"),
    os.getenv("OPENROUTER_API_KEY_5"),
    os.getenv("OPENROUTER_API_KEY_6"),
    os.getenv("OPENROUTER_API_KEY_7"),
]
OPENROUTER_API_KEYS = [k for k in OPENROUTER_API_KEYS if k]

SAVE_FILE = "zombie_save.json"

# ────────────────────────────────────────────────────────────
# Characters (EXACT data preserved from your original)
# ────────────────────────────────────────────────────────────
CHARACTER_INFO = {
    "Shaun Sadsarin": {"age": 15, "gender": "Male", "traits": ["empathetic","stubborn","agile","semi-reserved","improviser"], "siblings": ["Addison Sadsarin"], "likely_pairs": ["Addison Sadsarin","Aiden Muy","Gabe Muy","Dylan Pastorin"], "likely_conflicts": ["Jordan"]},
    "Addison Sadsarin": {"age": 16, "gender": "Female", "traits": ["kind","patient","responsible","lacks physicality","semi-obstinate"], "siblings": ["Shaun Sadsarin"], "likely_pairs": ["Ella Muy","Shaun Sadsarin","Dylan Pastorin"], "likely_conflicts": ["Jordan"]},
    "Dylan Pastorin": {"age": 16, "gender": "Male", "traits": ["romanticizes danger","unconventional","carefree","semi-reckless"], "siblings": [], "likely_pairs": ["Shaun Sadsarin","Jordan","Aiden Muy"], "likely_conflicts": ["Jordan"]},
    "Noah Nainggolan": {"age": 16, "gender": "Male", "traits": ["clever","insecure","witty","kind"], "siblings": ["Jill Nainggolan","Kate Nainggolan"], "likely_pairs": ["Vivian Muy","Ella Muy"], "likely_conflicts": ["Addison Sadsarin"]},
    "Jill Nainggolan": {"age": 15, "gender": "Female", "traits": ["emotional","kind","deeply protective","forgiving"], "siblings": ["Noah Nainggolan","Kate Nainggolan"], "likely_pairs": ["Nico Muy","Aiden Muy","Gabe Muy"], "likely_conflicts": ["Aiden Muy"]},
    "Kate Nainggolan": {"age": 14, "gender": "Female", "traits": ["quietly assertive","tough","brave","sharp","semi-harsh"], "siblings": ["Noah Nainggolan","Jill Nainggolan"], "likely_pairs": ["Gabe Muy","Nico Muy","Aiden Muy"], "likely_conflicts": ["Jordan"]},
    "Vivian Muy": {"age": 16, "gender": "Female", "traits": ["protective","strict","hard-headed","resilient","caring"], "siblings": ["Gabe Muy","Aiden Muy","Ella Muy","Nico Muy"], "likely_pairs": ["Noah Nainggolan","Shaun Sadsarin"], "likely_conflicts": ["Shaun Sadsarin"]},
    "Gabe Muy": {"age": 15, "gender": "Male", "traits": ["adventurous","decisive","sarcastic","bold"], "siblings": ["Vivian Muy","Aiden Muy","Ella Muy","Nico Muy"], "likely_pairs": ["Kate Nainggolan","Nico Muy","Addison Sadsarin"], "likely_conflicts": ["Addison Sadsarin"]},
    "Aiden Muy": {"age": 14, "gender": "Male", "traits": ["fiery","strong-willed","loyal","headstrong"], "siblings": ["Vivian Muy","Gabe Muy","Ella Muy","Nico Muy"], "likely_pairs": ["Dylan Pastorin","Jill Nainggolan","Shaun Sadsarin"], "likely_conflicts": ["Jill Nainggolan"]},
    "Ella Muy": {"age": 14, "gender": "Female", "traits": ["optimistic","creative","sensitive","cheerful"], "siblings": ["Vivian Muy","Gabe Muy","Aiden Muy","Nico Muy"], "likely_pairs": ["Addison Sadsarin","Noah Nainggolan"], "likely_conflicts": ["Shaun Sadsarin"]},
    "Nico Muy": {"age": 13, "gender": "Male", "traits": ["playful","resourceful","cautious","lighthearted"], "siblings": ["Vivian Muy","Gabe Muy","Aiden Muy","Ella Muy"], "likely_pairs": ["Jill Nainggolan","Kate Nainggolan","Jordan"], "likely_conflicts": ["Shaun Sadsarin"]},
    "Jordan": {"age": 13, "gender": "Male", "traits": ["easy-going","quietly skilled","funny"], "siblings": [], "likely_pairs": ["Nico Muy","Gabe Muy","Aiden Muy","Dylan Pastorin"], "likely_conflicts": ["Dylan Pastorin"]},
}

# Custom Discord emoji per character (your provided mapping)
HEALTH_EMOJI = {
    "Shaun Sadsarin": ":hawhar:",
    "Addison Sadsarin": ":feeling_silly:",
    "Dylan Pastorin": ":approved:",
    "Noah Nainggolan": ":sillynoah:",
    "Jill Nainggolan": ":que:",
    "Kate Nainggolan": ":sigma:",
    "Vivian Muy": ":leshame:",
    "Gabe Muy": ":zesty:",
    "Aiden Muy": ":aidun:",
    "Ella Muy": ":ellasigma:",
    "Nico Muy": ":sips_milk:",
    "Jordan": ":agua:",
}

ALL_NAMES: List[str] = list(CHARACTER_INFO.keys())

# Speed profiles (current_speed + get_delay())
SPEED_MAP = {1.0: 1.0, 1.5: 0.75, 2.0: 0.5}

# Borders: keep originals for all headers; only change ROUND END to have 🩸 inside text
HEADER_BORDER = "🩸━━━━━━━━━━━━━━━━━━━━━━━🩸"
ROUND_PLAIN_BORDER = "━━━━━━━━━━━━━━━━━━━━━━━"

# ────────────────────────────────────────────────────────────
# Regex + formatting helpers
# ────────────────────────────────────────────────────────────
def _bold_name_token(txt: str, token: str) -> str:
    # possessive first
    txt = re.sub(rf"(?<!\*)(?<!\w)({re.escape(token)})’s\b(?!\*)", r"**\1**’s", txt)
    txt = re.sub(rf"(?<!\*)(?<!\w)({re.escape(token)})'s\b(?!\*)", r"**\1**'s", txt)
    # then the token itself (avoid already bold)
    txt = re.sub(rf"(?<!\*)(?<!\w)({re.escape(token)})\b(?!\*)", r"**\1**", txt)
    return txt

def bold_character_names(s: str) -> str:
    result = s
    # full names first
    for name in ALL_NAMES:
        result = _bold_name_token(result, name)
    # then first names
    for name in ALL_NAMES:
        first = name.split()[0]
        result = _bold_name_token(result, first)
    return result

def ensure_bullet(line: str) -> str:
    t = line.strip()
    if not t:
        return ""
    return t if t.startswith("•") else f"• {t}"

def punctuation_guard(line: str) -> str:
    if not line:
        return line
    l = line.rstrip()
    if l[-1:] in ".!?…\"”'":
        return l
    return l + "."

def header_block(title: str) -> str:
    return f"{HEADER_BORDER}\n{title}\n{HEADER_BORDER}"

def round_end_header_centered(title: str) -> str:
    # Border has no emojis; emojis appear inside the centered line
    # We don't overcomplicate centering; Discord uses proportional font in embeds; simple pad looks fine.
    return f"{ROUND_PLAIN_BORDER}\n        🩸 {title} 🩸\n{ROUND_PLAIN_BORDER}"

# ────────────────────────────────────────────────────────────
# LLM client (OpenRouter)
# ────────────────────────────────────────────────────────────
_key_cooldowns: Dict[str, datetime] = {}

def _key_available(k: str) -> bool:
    t = _key_cooldowns.get(k)
    return (not t) or datetime.utcnow() >= t

def _cooldown_key(k: str, seconds: int = 60):
    _key_cooldowns[k] = datetime.utcnow() + timedelta(seconds=seconds)

async def llm_chat(messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 700) -> str:
    if not OPENROUTER_API_KEYS:
        raise RuntimeError("No OPENROUTER_API_KEYS configured.")
    last_err = None
    for key in OPENROUTER_API_KEYS:
        if not _key_available(key):
            continue
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
            if r.status_code == 429:
                _cooldown_key(key, 90)
                last_err = RuntimeError("Rate limited")
                continue
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            _cooldown_key(key, 60)
            continue
    raise last_err or RuntimeError("All keys failed.")

# ────────────────────────────────────────────────────────────
# Prompts — structured where needed (health JSON)
# ────────────────────────────────────────────────────────────
SCENE_PROMPT = """You are a terse, cinematic survival-horror narrator.
Characters: {names}
Write 6–8 bullets describing the next moment in the scene. Use exact full names or their first names naturally.
Return ONLY the bullets; each line must begin with '• ' (bullet) and contain a single sentence.
Avoid trailing commentary or headers.
"""

HEALTH_PROMPT = """Given the story so far, produce STRICT JSON for ONLY these survivor names (exact keys): {names}
For each key, return an object: {{"status":"green|yellow|red","desc":"short one-clause health note"}}
Return ONLY JSON, no codefence, no prose.
Example:
{{"Shaun Sadsarin": {{"status":"green","desc":"Healthy and alert"}}}}
"""

DILEMMA_PROMPT = """Describe exactly TWO bullets about the dilemma right now, each starting with '• ' and containing one sentence. No headers or extra text."""

CHOICES_PROMPT = """Return exactly two lines, each beginning with '• ' and formatted as '1. ...' and '2. ...'.
Each should be one sentence and mutually exclusive options."""

OUTCOME_PROMPT = """Write 3–5 bullets for the chosen option's outcome. Keep continuity with prior events.
If someone dies, include a bullet exactly containing 'X dies' (with X being the exact full name).
Each line: start with '• ' and one sentence. No extra text."""

# ────────────────────────────────────────────────────────────
# Game state + persistence
# ────────────────────────────────────────────────────────────
class GameState:
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.round = 1
        self.alive: List[str] = ALL_NAMES.copy()
        self.dead: List[str] = []
        self.speed: float = 1.0
        self.terminated: bool = False
        self.last_activity: datetime = datetime.utcnow()
        self.resume_note: Optional[str] = None
        # auto-tracking
        self.stats = {"helped": 0, "sinister": 0, "resourceful": 0, "dignified": 0}
        self.relationships = {"bonds": defaultdict(int), "conflicts": defaultdict(int)}

    def get_delay(self, base: float = 1.0) -> float:
        # current_speed + get_delay(): apply a multiplier that shortens delay as speed increases
        mult = SPEED_MAP.get(self.speed, 1.0)
        return base * mult

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "round": self.round,
            "alive": self.alive,
            "dead": self.dead,
            "speed": self.speed,
            "resume_note": self.resume_note,
            "stats": self.stats,
            "relationships": {
                "bonds": dict(self.relationships["bonds"]),
                "conflicts": dict(self.relationships["conflicts"]),
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        g = cls(d.get("channel_id", 0))
        g.round = d.get("round", 1)
        g.alive = d.get("alive", ALL_NAMES.copy())
        g.dead = d.get("dead", [])
        g.speed = float(d.get("speed", 1.0))
        g.resume_note = d.get("resume_note")
        g.stats = d.get("stats", {"helped": 0, "sinister": 0, "resourceful": 0, "dignified": 0})
        rel = d.get("relationships", {"bonds": {}, "conflicts": {}})
        bonds = defaultdict(int, rel.get("bonds", {}))
        conflicts = defaultdict(int, rel.get("conflicts", {}))
        g.relationships = {"bonds": bonds, "conflicts": conflicts}
        return g

def load_save(channel_id: int) -> Optional[GameState]:
    if not os.path.exists(SAVE_FILE):
        return None
    try:
        data = json.load(open(SAVE_FILE, "r", encoding="utf-8"))
        key = str(channel_id)
        if key in data:
            return GameState.from_dict(data[key])
    except Exception as e:
        logger.warning(f"Failed to load save: {e}")
    return None

def save_game(g: GameState):
    try:
        data = {}
        if os.path.exists(SAVE_FILE):
            try:
                data = json.load(open(SAVE_FILE, "r", encoding="utf-8"))
            except Exception:
                data = {}
        data[str(g.channel_id)] = g.to_dict()
        json.dump(data, open(SAVE_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save game: {e}")

# ────────────────────────────────────────────────────────────
# LLM helpers & parsers
# ────────────────────────────────────────────────────────────
def parse_bullets(s: str) -> List[str]:
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    out = []
    for ln in lines:
        core = ln.lstrip("• ").strip()
        out.append(ensure_bullet(punctuation_guard(core)))
    return out

def parse_health_json(s: str, alive: List[str]) -> Dict[str, Dict[str, str]]:
    try:
        data = json.loads(s)
        clean: Dict[str, Dict[str, str]] = {}
        for n in alive:
            v = data.get(n, {})
            if isinstance(v, dict) and "desc" in v and "status" in v:
                st = str(v.get("status", "")).lower()
                if st.startswith("g") or st.startswith("y") or st.startswith("r"):
                    clean[n] = {"status": st, "desc": str(v["desc"]).strip()}
        if clean:
            return clean
    except Exception:
        pass
    # If the model fails, provide neutral placeholders; icon selection will still be robust
    return {n: {"status": "green", "desc": "Status unclear"} for n in alive}

def status_icon(status: str, desc: str) -> str:
    # trust structured status primarily; small heuristic safety net
    st = (status or "").lower().strip()
    if st.startswith("g"):
        return "🟢"
    if st.startswith("y"):
        return "🟡"
    if st.startswith("r"):
        return "🔴"
    d = desc.lower()
    if any(w in d for w in ["wounded","bleeding","critical","dying","collapsed","unconscious","severe"]):
        return "🔴"
    if any(w in d for w in ["tired","injured","shaken","strained","exhausted","weak","dizzy","hurt","limping"]):
        return "🟡"
    if any(w in d for w in ["healthy","strong","fit","alert","ready","resilient","good","fine","okay","stable"]):
        return "🟢"
    return "🟢"  # never leave without a status

def format_health_lines(health_map: Dict[str, Dict[str, str]], alive_order: List[str]) -> List[str]:
    out: List[str] = []
    for name in alive_order:
        entry = health_map.get(name, {"status": "green", "desc": "Status unclear"})
        desc = entry.get("desc", "Status unclear")
        icon = status_icon(entry.get("status", "green"), desc)
        emj = HEALTH_EMOJI.get(name, "")
        # EXACT spacing: [status] [bolded name] [custom emoji] : [desc]
        out.append(f"{icon} {bold_character_names(name)} {emj} : {desc}")
    return out

def extract_deaths(bullets: List[str]) -> List[str]:
    # Match "X dies" (exact full name) or variants like "X is killed"
    pattern = re.compile(rf"\b({'|'.join(re.escape(n) for n in ALL_NAMES)})\b.*\b(dies|is killed|bleeds out|is dead)\b", re.I)
    results: List[str] = []
    for b in bullets:
        m = pattern.search(b)
        if m:
            results.append(m.group(1))
    # unique preserving order (most recent first if desired later)
    seen = set()
    ordered = []
    for n in results:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered

# Simple signals for stats/relationships auto-tracking
HELP_WORDS = ["pulls", "saves", "helps", "carries", "shields", "bandages", "patches"]
SINISTER_WORDS = ["threatens", "betrays", "abandons", "lies", "steals", "pushes"]
RESOURCEFUL_WORDS = ["plans", "crafts", "builds", "sets a trap", "improvises", "deciphers", "repairs"]
DIGNIFIED_WORDS = ["refuses to panic", "stands tall", "keeps calm", "reassures", "defends"]

def bump_auto_counters(g: GameState, text: str):
    s = text.lower()
    if any(w in s for w in HELP_WORDS):
        g.stats["helped"] += 1
    if any(w in s for w in SINISTER_WORDS):
        g.stats["sinister"] += 1
    if any(w in s for w in RESOURCEFUL_WORDS):
        g.stats["resourceful"] += 1
    if any(w in s for w in DIGNIFIED_WORDS):
        g.stats["dignified"] += 1
    # crude bonds/conflicts harvest
    for a in ALL_NAMES:
        a_first = a.split()[0].lower()
        for b in ALL_NAMES:
            if a == b: continue
            b_first = b.split()[0].lower()
            if f"{a_first} and {b_first}" in s or f"{a_first} with {b_first}" in s:
                g.relationships["bonds"][(a, b)] += 1
            if f"{a_first} vs {b_first}" in s or f"{a_first} against {b_first}" in s:
                g.relationships["conflicts"][(a, b)] += 1

# ────────────────────────────────────────────────────────────
# Streaming helpers
# ────────────────────────────────────────────────────────────
async def stream_bullets(channel: discord.TextChannel, bullets: List[str], delay: float, g: Optional[GameState] = None):
    """Edit-accumulate bullets into one message; enforce punctuation; robust to edit failures."""
    if not bullets:
        return
    try:
        msg = await channel.send("…")
    except Exception as e:
        logger.warning(f"Failed to send stream anchor: {e}")
        return

    content = ""
    for raw in bullets:
        if g and g.terminated:
            return
        if not raw:
            continue
        line = ensure_bullet(punctuation_guard(bold_character_names(raw)))
        # prevent double bullets/newlines
        if content:
            content = f"{content}\n{line}"
        else:
            content = line
        try:
            await msg.edit(content=content)
        except Exception as e:
            logger.warning(f"Edit failed, fallback send: {e}")
            try:
                await channel.send(line)
            except Exception:
                pass
        await asyncio.sleep(delay)

# ────────────────────────────────────────────────────────────
# Voting (early close after 5s inactivity)
# ────────────────────────────────────────────────────────────
async def vote_two_options(channel: discord.TextChannel, total_window: int = 30) -> Optional[int]:
    m = await channel.send("🗳️ React to vote (early close after 5s of no new reactions)…")
    for e in ("1️⃣", "2️⃣"):
        try:
            await m.add_reaction(e)
        except Exception:
            pass

    last_counts = (0, 0)
    last_change = datetime.utcnow()
    end_by = datetime.utcnow() + timedelta(seconds=total_window)

    while datetime.utcnow() < end_by:
        try:
            cur = await channel.fetch_message(m.id)
        except Exception:
            await asyncio.sleep(1)
            continue
        c1 = c2 = 0
        for r in cur.reactions:
            if r.emoji == "1️⃣":
                c1 = max(0, r.count - 1)  # minus bot
            elif r.emoji == "2️⃣":
                c2 = max(0, r.count - 1)
        if (c1, c2) != last_counts:
            last_counts = (c1, c2)
            last_change = datetime.utcnow()
        else:
            if (datetime.utcnow() - last_change).total_seconds() >= 5:
                break
        await asyncio.sleep(1)

    if last_counts == (0, 0):
        await channel.send("No votes received. The group hesitates too long… the night swallows them.")
        return None
    return 1 if last_counts[0] >= last_counts[1] else 2

# ────────────────────────────────────────────────────────────
# Cog
# ────────────────────────────────────────────────────────────
class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: Dict[int, GameState] = {}  # channel_id -> state

    # --------------- Commands (Slash + Legacy) ---------------
    @commands.hybrid_command(name="speed", with_app_command=True, description="Set pacing: 1.0 (normal), 1.5 (faster), 2.0 (fastest).")
    @app_commands.describe(value="Choose 1.0, 1.5, or 2.0")
    async def speed(self, ctx: commands.Context, value: float):
        if value not in (1.0, 1.5, 2.0):
            return await ctx.reply("Use one of: 1.0, 1.5, 2.0")
        chan = ctx.channel
        g = self.games.get(chan.id) or load_save(chan.id) or GameState(chan.id)
        g.speed = value
        self.games[chan.id] = g
        save_game(g)
        await ctx.reply(f"✅ Speed set to {value}x")

    @commands.hybrid_command(name="endzombie", with_app_command=True, description="End the current zombie game immediately.")
    async def endzombie(self, ctx: commands.Context):
        chan = ctx.channel
        g = self.games.get(chan.id) or load_save(chan.id)
        if not g:
            return await ctx.reply("No active game.")
        g.terminated = True
        save_game(g)
        await ctx.reply("🛑 Game ended.")

    @commands.hybrid_command(name="lizazombie", with_app_command=True, description="Start or resume the zombie survival game.")
    async def lizazombie(self, ctx: commands.Context):
        chan: discord.TextChannel = ctx.channel  # type: ignore
        if ZOMBIE_CHANNEL_ID and chan.id != ZOMBIE_CHANNEL_ID:
            return await ctx.reply("❌ This command is restricted to the dedicated zombie channel.")

        # Check for existing save and offer resume
        existing = load_save(chan.id)
        g: GameState
        if existing and not existing.terminated:
            class ResumeView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=25)
                    self.value: Optional[bool] = None

                @discord.ui.button(label="Continue last save", style=discord.ButtonStyle.green)
                async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.value = True
                    self.stop()
                    await interaction.response.defer()

                @discord.ui.button(label="Start new", style=discord.ButtonStyle.danger)
                async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.value = False
                    self.stop()
                    await interaction.response.defer()

            resume_desc = existing.resume_note or f"Round {existing.round}, survivors: {', '.join(existing.alive)}"
            await ctx.reply(f"Found a previous game:\n> {resume_desc}\nContinue?", view=(view := ResumeView()))
            await view.wait()
            if view.value is None:
                return await chan.send("Timed out. Cancelled.")
            g = existing if view.value else GameState(chan.id)
        else:
            g = GameState(chan.id)

        g.terminated = False
        self.games[chan.id] = g
        save_game(g)

        await chan.send("✅ Game starting…")
        await self.run_round_loop(chan, g)

    # --------------- Round loop ---------------
    async def run_round_loop(self, channel: discord.TextChannel, g: GameState):
        while not g.terminated:
            await self.run_single_round(channel, g)

    async def run_single_round(self, channel: discord.TextChannel, g: GameState):
        if g.terminated:
            return
        delay = g.get_delay(1.0)

        # Scene
        await channel.send(header_block(f"            Scene {g.round}"))
        scene_txt = await llm_chat([
            {"role": "system", "content": "You are a terse, cinematic survival-horror narrator."},
            {"role": "user", "content": SCENE_PROMPT.format(names=", ".join(g.alive))},
        ], temperature=0.85, max_tokens=500)
        scene_bullets = parse_bullets(scene_txt)
        await stream_bullets(channel, scene_bullets, delay, g)
        bump_auto_counters(g, "\n".join(scene_bullets))
        if g.terminated:
            save_game(g); return

        # Health (structured JSON)
        await channel.send(header_block("         Health Status"))
        health_json = await llm_chat([
            {"role": "system", "content": "Respond ONLY with strict JSON as instructed. No extra text."},
            {"role": "user", "content": HEALTH_PROMPT.format(names=", ".join(g.alive))},
        ], temperature=0.3, max_tokens=600)
        health_map = parse_health_json(health_json, g.alive)
        health_lines = format_health_lines(health_map, g.alive)
        await stream_bullets(channel, health_lines, delay, g)
        bump_auto_counters(g, "\n".join(health_lines))
        if g.terminated:
            save_game(g); return

        # Dilemma
        await channel.send(header_block(f"       Dilemma – Round {g.round}"))
        dilemma_txt = await llm_chat([
            {"role": "system", "content": "Write two compact bullets. No extra text."},
            {"role": "user", "content": DILEMMA_PROMPT},
        ], temperature=0.7, max_tokens=200)
        dilemma_bullets = parse_bullets(dilemma_txt)
        await stream_bullets(channel, dilemma_bullets, delay, g)
        bump_auto_counters(g, "\n".join(dilemma_bullets))
        if g.terminated:
            save_game(g); return

        # Choices
        await channel.send(header_block("            Choices"))
        choices_txt = await llm_chat([
            {"role": "system", "content": "Return exactly two bullets labeled '1.' and '2.'."},
            {"role": "user", "content": CHOICES_PROMPT},
        ], temperature=0.55, max_tokens=160)
        choice_bullets = parse_bullets(choices_txt)
        await stream_bullets(channel, choice_bullets, delay, g)
        bump_auto_counters(g, "\n".join(choice_bullets))
        if g.terminated:
            save_game(g); return

        # Vote (with early inactivity close)
        choice = await vote_two_options(channel, total_window=int(30 * max(0.5, delay)))
        if g.terminated or choice is None:
            g.terminated = True
            save_game(g)
            await channel.send("🛑 Game ended.")
            return

        # Outcome
        await channel.send(header_block("            Outcome"))
        outcome_txt = await llm_chat([
            {"role": "system", "content": "Write punchy, one-sentence bullets. Preserve continuity."},
            {"role": "user", "content": f"Chosen option: {choice}. {OUTCOME_PROMPT}"},
        ], temperature=0.9, max_tokens=400)
        outcome_bullets = parse_bullets(outcome_txt)
        await stream_bullets(channel, outcome_bullets, delay, g)
        bump_auto_counters(g, "\n".join(outcome_bullets))
        if g.terminated:
            save_game(g); return

        # Sync deaths ↔ survivors
        described_deaths = extract_deaths(outcome_bullets)
        for who in described_deaths:
            if who in g.alive:
                g.alive.remove(who)
            if who not in g.dead:
                g.dead.insert(0, who)

        # Fallback survivor logic: if outcome accidentally lists no survivors or wipes all, keep prior survivors
        if not g.alive:
            # ensure at least someone survives if the story didn't decide
            # (pick the last two who weren't explicitly killed this round)
            still = [n for n in ALL_NAMES if n not in g.dead]
            g.alive = still if still else []

        # Summary
        await channel.send(header_block("         Game Summary"))
        deaths_list = g.dead if g.dead else ["None"]
        death_lines = [ensure_bullet(f"{name}.") for name in deaths_list]
        await channel.send("🪦 Deaths (most recent first)")
        await stream_bullets(channel, death_lines, delay * 0.8, g)

        # Round end header (no emojis on the borders; emojis inside centered line)
        await channel.send(round_end_header_centered(f"End of Round {g.round}"))

        # Prepare next round
        g.round += 1
        g.resume_note = f"After Round {g.round-1}, survivors: {', '.join(g.alive) if g.alive else 'None'}"
        save_game(g)

    # --------------- Error handler to ensure no duplicate registration crashes ---------------
    @commands.Cog.listener()
    async def on_error(self, event_method: str, *args, **kwargs):
        logger.exception(f"Error in event {event_method}", exc_info=True)

# ────────────────────────────────────────────────────────────
# Cog setup (no duplicate registration)
# ────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    # add_cog is idempotent across reloads in latest discord.py when using setup hooks properly
    await bot.add_cog(ZombieGame(bot))
