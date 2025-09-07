import os
import re
import json
import httpx
import asyncio
import logging
import random
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Optional, Tuple

import discord
from discord.ext import commands
from discord import app_commands, Interaction

# ───────────────────────────────────────────────────────────
# 🔧 Logging
# ───────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zombie_game")

# ───────────────────────────────────────────────────────────
# 🌱 Environment / Config
# ───────────────────────────────────────────────────────────
ZOMBIE_CHANNEL_ID = int(os.getenv("ZOMBIE_CHANNEL_ID", "0"))
MODEL = os.getenv("MODEL", "meta-llama/llama-3.1-70b-instruct:free")

# 7 keys supported (rotation + cooldown)
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
KEY_COOLDOWNS: Dict[str, datetime] = {}

SAVE_FILE = "zombie_save.json"

# ───────────────────────────────────────────────────────────
# 🧍 Characters (exact from original)
# ───────────────────────────────────────────────────────────
CHARACTER_INFO: Dict[str, Dict] = {
    "Shaun Sadsarin": {
        "age": 15, "gender": "Male",
        "traits": ["empathetic", "stubborn", "agile", "semi-reserved", "improviser"],
        "siblings": ["Addison Sadsarin"],
        "likely_pairs": ["Addison Sadsarin", "Aiden Muy", "Gabe Muy", "Dylan Pastorin"],
        "likely_conflicts": ["Jordan"]
    },
    "Addison Sadsarin": {
        "age": 16, "gender": "Female",
        "traits": ["kind", "patient", "responsible", "lacks physicality", "semi-obstinate"],
        "siblings": ["Shaun Sadsarin"],
        "likely_pairs": ["Kate Nainggolan", "Jill Nainggolan", "Shaun Sadsarin", "Vivian Muy"],
        "likely_conflicts": ["Dylan Pastorin"]
    },
    "Dylan Pastorin": {
        "age": 21, "gender": "Male",
        "traits": ["confident", "wannabe-gunner", "brash", "slow", "semi-manipulable", "extrovert"],
        "siblings": [],
        "likely_pairs": ["Noah Nainggolan", "Gabe Muy", "Shaun Sadsarin", "Vivian Muy"],
        "likely_conflicts": ["Kate Nainggolan"]
    },
    "Noah Nainggolan": {
        "age": 18, "gender": "Male",
        "traits": ["spontaneous", "weeaboo", "semi-aloof", "brawler"],
        "siblings": ["Kate Nainggolan", "Jill Nainggolan"],
        "likely_pairs": ["Gabe Muy", "Jill Nainggolan", "Kate Nainggolan", "Dylan Pastorin"],
        "likely_conflicts": ["Jill Nainggolan"]
    },
    "Jill Nainggolan": {
        "age": 16, "gender": "Female",
        "traits": ["conniving", "demure", "mellow", "swimmer"],
        "siblings": ["Kate Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Kate Nainggolan", "Noah Nainggolan", "Addison Sadsarin", "Gabe Muy"],
        "likely_conflicts": ["Noah Nainggolan"]
    },
    "Kate Nainggolan": {
        "age": 14, "gender": "Female",
        "traits": ["cheeky", "manipulative", "bold", "persuasive"],
        "siblings": ["Jill Nainggolan", "Noah Nainggolan"],
        "likely_pairs": ["Dylan Pastorin", "Gabe Muy", "Addison Sadsarin", "Shaun Sadsarin"],
        "likely_conflicts": ["Aiden Muy"]
    },
    "Vivian Muy": {
        "age": 18, "gender": "Female",
        "traits": ["wise", "calm", "insightful", "secret genius"],
        "siblings": ["Gabe Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Dylan Pastorin", "Ella Muy", "Aiden Muy", "Addison Sadsarin"],
        "likely_conflicts": ["Gabe Muy"]
    },
    "Gabe Muy": {
        "age": 17, "gender": "Male",
        "traits": ["wrestler", "peacekeeper", "withdraws under pressure", "light-weight"],
        "siblings": ["Vivian Muy", "Aiden Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Aiden Muy", "Nico Muy", "Shaun Sadsarin", "Noah Nainggolan"],
        "likely_conflicts": ["Addison Sadsarin"]
    },
    "Aiden Muy": {
        "age": 14, "gender": "Male",
        "traits": ["crafty", "short", "observant", "chef"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Ella Muy", "Nico Muy"],
        "likely_pairs": ["Shaun Sadsarin", "Jordan", "Nico Muy", "Addison Sadsarin"],
        "likely_conflicts": ["Ella Muy"]
    },
    "Ella Muy": {
        "age": 11, "gender": "Female",
        "traits": ["physically reliant", "luckiest"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Nico Muy"],
        "likely_pairs": ["Addison Sadsarin", "Jill Nainggolan", "Kate Nainggolan", "Vivian Muy"],
        "likely_conflicts": ["Shaun Sadsarin"]
    },
    "Nico Muy": {
        "age": 12, "gender": "Male",
        "traits": ["daring", "comical", "risk-taker", "needs guidance"],
        "siblings": ["Vivian Muy", "Gabe Muy", "Aiden Muy", "Ella Muy"],
        "likely_pairs": ["Jordan", "Aiden Muy", "Gabe Muy", "Shaun Sadsarin"],
        "likely_conflicts": ["Vivian Muy"]
    },
    "Jordan": {
        "age": 13, "gender": "Male",
        "traits": ["easy-going", "quietly skilled", "funny"],
        "siblings": [],
        "likely_pairs": ["Nico Muy", "Gabe Muy", "Aiden Muy", "Dylan Pastorin"],
        "likely_conflicts": ["Dylan Pastorin"]
    }
}
CHARACTERS: List[str] = list(CHARACTER_INFO.keys())

# Discord custom emoji map for Health section
HEALTH_EMOJI: Dict[str, str] = {
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

# ───────────────────────────────────────────────────────────
# ⏱️ Speed control (affects pacing of bullet stream)
# ───────────────────────────────────────────────────────────
ALLOWED_SPEEDS = {1.0, 1.5, 2.0}

def get_delay(base: float, speed: float) -> float:
    # Higher speed => shorter delay
    if speed not in ALLOWED_SPEEDS:
        speed = 1.0
    return max(0.05, base / speed)

# ───────────────────────────────────────────────────────────
# 💾 Save / Load
# ───────────────────────────────────────────────────────────
def safe_load_json(path: str) -> Optional[dict]:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load save: {e}")
        return None

def safe_save_json(path: str, data: dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save: {e}")

# ───────────────────────────────────────────────────────────
# 🔑 OpenRouter (key rotation + cooldown)
# ───────────────────────────────────────────────────────────
def key_on_cooldown(key: str) -> bool:
    return key in KEY_COOLDOWNS and datetime.utcnow() < KEY_COOLDOWNS[key]

def set_key_cooldown(key: str, seconds: int = 600):
    KEY_COOLDOWNS[key] = datetime.utcnow() + timedelta(seconds=seconds)

async def send_openrouter(payload: dict) -> Optional[dict]:
    tried: set = set()
    for key in OPENROUTER_API_KEYS:
        if not key or key in tried:
            continue
        if key_on_cooldown(key):
            logger.info(f"Skipping cooldown key: {key[:6]}•••")
            continue
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                r.raise_for_status()
                return r.json()
        except httpx.HTTPStatusError as e:
            tried.add(key)
            code = e.response.status_code
            logger.warning(f"OpenRouter key {key[:6]}••• failed with {code}")
            if code in (401, 429, 503):
                set_key_cooldown(key, 600)
                continue
            else:
                continue
        except Exception as e:
            tried.add(key)
            logger.warning(f"OpenRouter network error on {key[:6]}•••: {e}")
            continue
    return None

async def ai(messages: List[dict], temperature: float = 0.8) -> Optional[str]:
    payload = {"model": MODEL, "messages": messages, "temperature": temperature}
    data = await send_openrouter(payload)
    if not data:
        return None
    return (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    ) or None

# ───────────────────────────────────────────────────────────
# 🧠 Game State
# ───────────────────────────────────────────────────────────
class GameState:
    def __init__(self, initiator_id: int):
        self.initiator = initiator_id
        self.round_number: int = 1
        self.alive: List[str] = CHARACTERS.copy()
        self.dead: List[str] = []
        self.last_choice: Optional[str] = None
        self.last_events: str = ""
        self.story_context: str = ""
        self.options: List[str] = []
        self.votes: Dict[str, int] = {}
        self.current_speed: float = 1.0  # speed multiplier (1.0 / 1.5 / 2.0)
        self.terminated: bool = False
        self.since_last_vote_activity: Optional[datetime] = None

        # Stats + relationships
        self.stats = {
            "helped": defaultdict(int),
            "resourceful": defaultdict(int),
            "sinister": defaultdict(int),
            "dignified": defaultdict(int),
            "bonds": defaultdict(int),        # key: (A,B)
            "conflicts": defaultdict(int),    # key: (A,B)
        }

    def snapshot(self) -> dict:
        return {
            "initiator": self.initiator,
            "round_number": self.round_number,
            "alive": self.alive,
            "dead": self.dead,
            "last_choice": self.last_choice,
            "last_events": self.last_events,
            "story_context": self.story_context,
            "current_speed": self.current_speed,
            "stats": {
                "helped": dict(self.stats["helped"]),
                "resourceful": dict(self.stats["resourceful"]),
                "sinister": dict(self.stats["sinister"]),
                "dignified": dict(self.stats["dignified"]),
                "bonds": {f"{a}|{b}": v for (a, b), v in self.stats["bonds"].items()},
                "conflicts": {f"{a}|{b}": v for (a, b), v in self.stats["conflicts"].items()},
            },
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> "GameState":
        g = cls(initiator_id=data.get("initiator", 0))
        g.round_number = data.get("round_number", 1)
        g.alive = data.get("alive", CHARACTERS.copy())
        g.dead = data.get("dead", [])
        g.last_choice = data.get("last_choice")
        g.last_events = data.get("last_events", "")
        g.story_context = data.get("story_context", "")
        g.current_speed = data.get("current_speed", 1.0)
        stats = data.get("stats", {})
        for k in ("helped", "resourceful", "sinister", "dignified"):
            for name, v in stats.get(k, {}).items():
                g.stats[k][name] = v
        for pair_str, v in stats.get("bonds", {}).items():
            a, b = pair_str.split("|", 1)
            g.stats["bonds"][(a, b)] = v
        for pair_str, v in stats.get("conflicts", {}).items():
            a, b = pair_str.split("|", 1)
            g.stats["conflicts"][(a, b)] = v
        return g

# Singleton active game
active_game: Optional[GameState] = None

def is_active() -> bool:
    return active_game is not None and not active_game.terminated

def end_game():
    global active_game
    if active_game:
        active_game.terminated = True

# ───────────────────────────────────────────────────────────
# 🔤 Text helpers
# ───────────────────────────────────────────────────────────
def bold_name(name: str) -> str:
    return f"**{name}**"

def _bold_exact_word(text: str, word: str) -> str:
    # Bold the word and possessive forms if not already bolded
    # Use negative lookbehind/ahead to avoid double bolding
    pattern_possessive = rf"(?<!\*)\b({re.escape(word)})'s\b(?!\*)"
    text = re.sub(pattern_possessive, r"**\1**'s", text)
    pattern_word = rf"(?<!\*)\b({re.escape(word)})\b(?!\*)"
    text = re.sub(pattern_word, r"**\1**", text)
    return text

def bold_character_names(text: str) -> str:
    # Bold full names first, then first names
    for full in CHARACTER_INFO:
        text = _bold_exact_word(text, full)
    for full in CHARACTER_INFO:
        first = full.split()[0]
        text = _bold_exact_word(text, first)
    return text

def ensure_sentence_punct(s: str) -> str:
    s = s.rstrip()
    if not s:
        return s
    if s[-1] in ".!?…\"””'":
        return s
    return s + "."

def ensure_single_bullet(line: str) -> str:
    # Normalize bullet prefix
    stripped = line.strip()
    stripped = stripped.lstrip("*-•").strip()
    return f"• {stripped}"

def split_sentences(text: str) -> List[str]:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]

def normalize_bullets(text: str) -> List[str]:
    # Turn any text into clean bullets, enforce punctuation, avoid doubles
    lines = [l for l in text.splitlines() if l.strip()]
    bullets: List[str] = []
    buf = ""
    for line in lines:
        raw = line.strip()
        if raw.startswith(("•", "-", "*")):
            if buf.strip():
                bullets.append(ensure_single_bullet(ensure_sentence_punct(buf)))
            buf = raw.lstrip("*-• ").strip()
            bullets.append(ensure_single_bullet(ensure_sentence_punct(buf)))
            buf = ""
        else:
            if buf:
                buf += " " + raw
            else:
                buf = raw
    if buf.strip():
        bullets.append(ensure_single_bullet(ensure_sentence_punct(buf)))
    # De-duplicate accidental consecutive duplicates
    cleaned: List[str] = []
    for b in bullets:
        if not cleaned or cleaned[-1] != b:
            cleaned.append(b)
    return cleaned

def center_header(text: str, width: int = 31) -> str:
    # Create centered line between bars with no emojis
    line = "━" * width
    pad_total = max(0, width - len(text))
    left = pad_total // 2
    right = pad_total - left
    centered = f"{' ' * left}{text}{' ' * right}"
    return f"{line}\n{centered}\n{line}"

# ───────────────────────────────────────────────────────────
# 📈 Auto Tracking
# ───────────────────────────────────────────────────────────
HELP_WORDS = r"(help|assist|protect|save)"
RES_WORDS  = r"(improvise|solve|navigate|strategize|repair|hack|cook)"
SIN_WORDS  = r"(betray|attack|abandon|sabotage|threaten|lie)"
DIG_WORDS  = r"(grace|sacrifice|honor|calm|mercy)"

def auto_track_stats(text: str, g: GameState):
    if not text:
        return
    for n in CHARACTER_INFO:
        # Use flexible "name ... word" and "word ... name"
        if re.search(rf"{re.escape(n)}.*{HELP_WORDS}|{HELP_WORDS}.*{re.escape(n)}", text, re.IGNORECASE):
            g.stats["helped"][n] += 1
        if re.search(rf"{re.escape(n)}.*{RES_WORDS}|{RES_WORDS}.*{re.escape(n)}", text, re.IGNORECASE):
            g.stats["resourceful"][n] += 1
        if re.search(rf"{re.escape(n)}.*{SIN_WORDS}|{SIN_WORDS}.*{re.escape(n)}", text, re.IGNORECASE):
            g.stats["sinister"][n] += 1
        if re.search(rf"{re.escape(n)}.*{DIG_WORDS}|{DIG_WORDS}.*{re.escape(n)}", text, re.IGNORECASE):
            g.stats["dignified"][n] += 1

def auto_track_relationships(text: str, g: GameState):
    if not text:
        return
    alive = [n for n in g.alive if n in text]
    for i, a in enumerate(alive):
        for b in alive[i+1:]:
            # Bonds
            if re.search(rf"{re.escape(a)}.*(share|nod|exchange|trust|hug|hold).+{re.escape(b)}", text, re.IGNORECASE) or \
               re.search(rf"{re.escape(b)}.*(share|nod|exchange|trust|hug|hold).+{re.escape(a)}", text, re.IGNORECASE):
                g.stats["bonds"][(a, b)] += 1
            # Conflicts
            if re.search(rf"{re.escape(a)}.*(argue|fight|oppose|resent|shout|blame).+{re.escape(b)}", text, re.IGNORECASE) or \
               re.search(rf"{re.escape(b)}.*(argue|fight|oppose|resent|shout|blame).+{re.escape(a)}", text, re.IGNORECASE):
                g.stats["conflicts"][(a, b)] += 1

def get_top_or_none(d: Dict) -> Optional[str]:
    if not d:
        return None
    return max(d.items(), key=lambda x: x[1])[0]

# ───────────────────────────────────────────────────────────
# 🧪 Outcome parsing -> sync deaths/survivors
# ───────────────────────────────────────────────────────────
DEATH_HINTS = r"(dies|dead|perish|devour|bitten|torn|crushed|dragged|seized|vanish|bleeds out|last breath|no pulse)"

def parse_outcome_lists(raw_outcome: str, prev_alive: List[str]) -> Tuple[List[str], List[str]]:
    # Extract explicit "Deaths:" and "Survivors:" blocks if present
    deaths_block = re.search(r"Deaths:\s*(.+?)(?:\n\S|$)", raw_outcome, re.IGNORECASE | re.DOTALL)
    survivors_block = re.search(r"Survivors:\s*(.+?)(?:\n\S|$)", raw_outcome, re.IGNORECASE | re.DOTALL)

    def names_from_block(block: Optional[re.Match]) -> List[str]:
        if not block:
            return []
        text = block.group(1)
        # Accept either "• Name" bullets or comma-separated
        cand = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            line = line.lstrip("*-• ").strip()
            if "," in line:
                cand.extend([x.strip() for x in line.split(",") if x.strip()])
            else:
                cand.append(line)
        # Filter to valid character names
        out = []
        for token in cand:
            # Sometimes bold or extra punctuation
            token = re.sub(r"[*_~`]|[.!,;:]+$", "", token).strip()
            # match full name by startswith first name
            matches = [n for n in CHARACTER_INFO if token.lower() in (n.lower(), n.split()[0].lower()) or token.lower() == n.lower()]
            if matches:
                # take first best match
                out.append(matches[0])
        return list(dict.fromkeys(out))

    deaths = names_from_block(deaths_block)
    survivors = names_from_block(survivors_block)

    # If no explicit lists, infer deaths from narration
    if not deaths:
        for n in prev_alive:
            if re.search(rf"{re.escape(n)}.*{DEATH_HINTS}", raw_outcome, re.IGNORECASE) or \
               re.search(rf"{n.split()[0]}\b.*{DEATH_HINTS}", raw_outcome, re.IGNORECASE):
                deaths.append(n)

    # If survivors not listed, derive as prev_alive minus deaths
    if not survivors:
        survivors = [n for n in prev_alive if n not in deaths]

    # Fallback survivor logic: ensure at least one survivor if possible
    if not survivors and deaths:
        still_alive = [n for n in prev_alive if n not in deaths]
        if still_alive:
            survivors = [random.choice(still_alive)]

    # De-dup + ensure disjoint
    deaths = [n for n in dict.fromkeys(deaths) if n in prev_alive]
    survivors = [n for n in dict.fromkeys(survivors) if n in prev_alive and n not in deaths]
    return deaths, survivors

# ───────────────────────────────────────────────────────────
# 🖨️ Streaming
# ───────────────────────────────────────────────────────────
async def stream_bullets(channel: discord.TextChannel, bullets: List[str], base_delay: float, speed: float):
    # Sends/edits a single message; enforces punctuation; handles errors; ensures single bullets
    if not bullets:
        return
    bullets = [ensure_single_bullet(ensure_sentence_punct(b.lstrip("*-• "))) for b in bullets if b and b.strip()]
    content = ""
    try:
        msg = await channel.send("…")
    except Exception as e:
        logger.warning(f"Failed to create message for streaming: {e}")
        return

    for b in bullets:
        if len(content) + len(b) + 2 > 1900:  # send a new message if too long
            try:
                await msg.edit(content=content.strip())
                msg = await channel.send("…")
                content = ""
            except Exception as e:
                logger.warning(f"Edit failed mid-stream: {e}")
                return
        content += b + "\n\n"
        try:
            await msg.edit(content=content.strip())
        except Exception as e:
            logger.warning(f"Edit failed: {e}")
            return
        await asyncio.sleep(get_delay(base_delay, speed))

# ───────────────────────────────────────────────────────────
# 🩺 Health formatting (ONLY place using status icons + custom emojis)
# ───────────────────────────────────────────────────────────
def health_status_icon(index: int, total: int) -> str:
    # Based on survivor index position (top third = green, middle = yellow, bottom = red)
    if total <= 0:
        return "🟢"
    tercile = total // 3 or 1
    if index < tercile:
        return "🟢"
    elif index < 2 * tercile:
        return "🟡"
    else:
        return "🔴"

def format_health_bullets(raw_health: str, alive_order: List[str]) -> List[str]:
    # Build mapping name -> short desc (first 2–5 words)
    # Accept either bullets or lines "Name: desc"
    lines = [l.strip() for l in raw_health.splitlines() if l.strip()]
    pairs: Dict[str, str] = {}
    for ln in lines:
        ln = ln.lstrip("*-• ").strip()
        # Try "Name: desc"
        if ":" in ln:
            name_part, desc = ln.split(":", 1)
            name_part = re.sub(r"[*_~`]", "", name_part).strip()
            desc = re.sub(r"[*_~`]", "", desc).strip()
            # pick best match for name
            candidates = [n for n in CHARACTER_INFO if name_part.lower() in (n.lower(), n.split()[0].lower())]
            if candidates:
                name = candidates[0]
                short_desc = " ".join(desc.split()[:7]).rstrip(",.")
                pairs[name] = short_desc
        else:
            # Maybe starts with a name
            for n in CHARACTER_INFO:
                if ln.lower().startswith(n.lower()) or ln.lower().startswith(n.split()[0].lower()):
                    short = re.sub(rf"(?i)^{re.escape(n)}['’]s", "", ln)  # strip "Name's"
                    short = re.sub(rf"(?i)^{n.split()[0]}['’]s", "", short)
                    short = re.sub(rf"(?i)^{re.escape(n)}", "", short).strip(":-—–, ")
                    short = re.sub(rf"(?i)^{n.split()[0]}", "", short).strip(":-—–, ")
                    pairs[n] = " ".join(short.split()[:7]).rstrip(",.")
                    break

    # Default "No status reported" for missing alive
    for n in alive_order:
        if n not in pairs:
            pairs[n] = "no status reported"

    total = len(alive_order)
    bullets: List[str] = []
    for idx, n in enumerate(alive_order):
        icon = health_status_icon(idx, total)
        emoji = HEALTH_EMOJI.get(n, "")
        # [status color] [name] [emoji]: [desc],
        line = f"{icon} {bold_name(n)} {emoji}: {pairs[n]},"
        bullets.append(ensure_single_bullet(line))
    return bullets

# ───────────────────────────────────────────────────────────
# 🧾 Prompt builders
# ───────────────────────────────────────────────────────────
def build_scene_prompt(g: GameState) -> str:
    traits = "\n".join([f"{n}: {', '.join(CHARACTER_INFO[n]['traits'])}" for n in g.alive])
    return (
        "You are a horror storyteller for a Discord text game. "
        "Output ONLY text; no images or image suggestions. "
        "Write a tense cinematic continuation involving all alive characters. "
        "Use short bullet points starting with •. "
        "Keep total length under 1400 characters.\n\n"
        f"Alive: {', '.join(g.alive)}\n"
        f"Dead: {', '.join(g.dead)}\n"
        f"Traits:\n{traits}\n\n"
        f"Context so far:\n{g.story_context[-1800:]}\n"
    )

def build_health_prompt(g: GameState) -> str:
    return (
        "You are describing each alive character's physical condition in 2–7 words. "
        "Do not include dead characters. "
        "Return each as a bullet starting with • in the form \"Name: descriptor\".\n\n"
        f"Alive: {', '.join(g.alive)}\n"
        f"Dead: {', '.join(g.dead)}\n"
        f"Context:\n{g.story_context[-1200:]}\n"
    )

def build_dilemma_prompt(g: GameState, scene_text: str, health_text: str) -> str:
    return (
        "Based on the scene and health, return EXACTLY two bullets (starting with •) "
        "that describe the new problem facing the group. No options, no numbers, no meta.\n\n"
        f"Scene:\n{scene_text}\n\n"
        f"Health:\n{health_text}\n"
    )

def build_choices_prompt(g: GameState, dilemma_text: str) -> str:
    return (
        "Return EXACTLY two numbered choices (1. and 2.) the group could take next, "
        "one concise sentence each, no extra commentary.\n\n"
        f"Dilemma:\n{dilemma_text}\n"
    )

def build_outcome_prompt(g: GameState, choice_text: str, scene_text: str) -> str:
    return (
        "Describe the consequences of the chosen action in tense, vivid bullets (•). "
        "If someone dies, explicitly add a 'Deaths:' line listing names. "
        "Optionally add a 'Survivors:' line listing remaining names. "
        "Do NOT revive dead characters.\n\n"
        f"Choice: {choice_text}\n"
        f"Alive before outcome: {', '.join(g.alive)}\n"
        f"Dead: {', '.join(g.dead)}\n"
        f"Recent Scene:\n{scene_text}\n"
    )

# ───────────────────────────────────────────────────────────
# 🎮 Round Phases
# ───────────────────────────────────────────────────────────
async def generate_scene(g: GameState) -> Optional[str]:
    content = await ai(
        [
            {"role": "system", "content": "You are a horror narrator. Output ONLY text."},
            {"role": "user", "content": build_scene_prompt(g)},
        ],
        temperature=0.85,
    )
    if not content:
        return None
    auto_track_stats(content, g)
    auto_track_relationships(content, g)
    return content

async def generate_health(g: GameState) -> Optional[str]:
    content = await ai(
        [
            {"role": "system", "content": "You output bullet points for health. ONLY text."},
            {"role": "user", "content": build_health_prompt(g)},
        ],
        temperature=0.6,
    )
    if not content:
        return None
    return content

async def generate_dilemma(g: GameState, scene_text: str, health_text: str) -> Optional[str]:
    content = await ai(
        [
            {"role": "system", "content": "You output ONLY bullets (•)."},
            {"role": "user", "content": build_dilemma_prompt(g, scene_text, health_text)},
        ],
        temperature=0.9,
    )
    return content

async def generate_choices(g: GameState, dilemma_text: str) -> Optional[str]:
    content = await ai(
        [
            {"role": "system", "content": "You output EXACTLY two numbered options (1., 2.)."},
            {"role": "user", "content": build_choices_prompt(g, dilemma_text)},
        ],
        temperature=0.8,
    )
    return content

async def generate_outcome(g: GameState, choice_text: str, scene_text: str) -> Optional[str]:
    content = await ai(
        [
            {"role": "system", "content": "You output ONLY text. Use bullets for narration."},
            {"role": "user", "content": build_outcome_prompt(g, choice_text, scene_text)},
        ],
        temperature=0.85,
    )
    return content

# ───────────────────────────────────────────────────────────
# 🗳️ Voting helpers (early-close after 5s inactivity)
# ───────────────────────────────────────────────────────────
async def collect_votes(bot: commands.Bot, message: discord.Message, inactivity_seconds: int = 5, max_total: int = 30) -> Dict[str, int]:
    """Add reactions, then watch for reaction_add events. Close when no new activity for 5s or when max_total reached."""
    votes = {"1️⃣": 0, "2️⃣": 0}
    for e in ("1️⃣", "2️⃣"):
        try:
            await message.add_reaction(e)
        except Exception:
            pass

    start = datetime.utcnow()
    last_activity = datetime.utcnow()

    def check(payload: discord.RawReactionActionEvent):
        return payload.message_id == message.id and str(payload.emoji) in ("1️⃣", "2️⃣")

    # Prime counts by reading current reactions (in case someone insta-clicked)
    await asyncio.sleep(0.5)
    try:
        msg = await message.channel.fetch_message(message.id)
        for r in msg.reactions:
            if str(r.emoji) in votes:
                # subtract bot if present
                count = r.count
                async for u in r.users():
                    if u.bot:
                        count -= 1
                        break
                votes[str(r.emoji)] = max(0, count)
    except Exception:
        pass

    while (datetime.utcnow() - start).total_seconds() < max_total:
        try:
            payload: discord.RawReactionActionEvent = await bot.wait_for("raw_reaction_add", timeout=inactivity_seconds, check=check)
            last_activity = datetime.utcnow()
            # Re-fetch to get accurate counts (handles removes + adds)
            msg = await message.channel.fetch_message(message.id)
            for r in msg.reactions:
                if str(r.emoji) in votes:
                    count = r.count
                    async for u in r.users():
                        if u.bot:
                            count -= 1
                            break
                    votes[str(r.emoji)] = max(0, count)
        except asyncio.TimeoutError:
            # No activity in inactivity_seconds -> early close
            break

    return votes

# ───────────────────────────────────────────────────────────
# 🧟 Core loop
# ───────────────────────────────────────────────────────────
async def run_round(bot: commands.Bot, channel: discord.TextChannel, g: GameState):
    # SCENE
    scene_raw = await generate_scene(g)
    if not scene_raw:
        await channel.send("⚠️ Scene generation failed.")
        end_game()
        return
    scene_bullets = normalize_bullets(bold_character_names(scene_raw))
    await channel.send(center_header(f"Scene {g.round_number}"))
    await stream_bullets(channel, scene_bullets, base_delay=4.5, speed=g.current_speed)

    # HEALTH
    health_raw = await generate_health(g)
    if not health_raw:
        await channel.send("⚠️ Health generation failed.")
        end_game()
        return
    health_bullets = format_health_bullets(health_raw, g.alive)
    await channel.send(center_header("Health Status"))
    await stream_bullets(channel, health_bullets, base_delay=1.6, speed=g.current_speed)

    # DILEMMA
    dilemma_raw = await generate_dilemma(g, "\n".join(scene_bullets), health_raw)
    if not dilemma_raw:
        await channel.send("⚠️ Dilemma generation failed.")
        end_game()
        return
    dilemma_bullets = normalize_bullets(bold_character_names(dilemma_raw))
    # Ensure exactly two bullets
    if len(dilemma_bullets) > 2:
        dilemma_bullets = dilemma_bullets[:2]
    await channel.send(center_header(f"Dilemma – Round {g.round_number}"))
    await stream_bullets(channel, dilemma_bullets, base_delay=4.7, speed=g.current_speed)

    # CHOICES
    choices_raw = await generate_choices(g, "\n".join(dilemma_bullets))
    if not choices_raw:
        await channel.send("⚠️ Choice generation failed.")
        end_game()
        return
    # Get exactly two numbered lines
    lines = [l.strip() for l in choices_raw.splitlines() if l.strip()]
    numbered = [l for l in lines if l.startswith("1.") or l.startswith("2.")]
    if len(numbered) != 2:
        # Fallback: best two non-empty
        numbered = [f"1. {lines[0]}", f"2. {lines[1]}"] if len(lines) >= 2 else [f"1. Option A", f"2. Option B"]
    g.options = numbered
    await channel.send(center_header("Choices"))
    await stream_bullets(channel, numbered, base_delay=3.8, speed=g.current_speed)

    # VOTE
    vote_msg = await channel.send("🗳️ React to vote (early close after 5s of no new reactions)…")
    votes = await collect_votes(bot, vote_msg, inactivity_seconds=5, max_total=30)
    if votes["1️⃣"] == 0 and votes["2️⃣"] == 0:
        await channel.send("No votes received. The group hesitates too long… the night swallows them.")
        end_game()
        return
    g.last_choice = g.options[0] if votes["1️⃣"] >= votes["2️⃣"] else g.options[1]

    # OUTCOME
    outcome_raw = await generate_outcome(g, g.last_choice, "\n".join(scene_bullets))
    if not outcome_raw:
        await channel.send("⚠️ Outcome generation failed.")
        end_game()
        return

    # Sync deaths/survivors to game state
    found_deaths, found_survivors = parse_outcome_lists(outcome_raw, g.alive.copy())
    # Update lists
    for d in found_deaths:
        if d in g.alive:
            g.alive.remove(d)
        if d not in g.dead:
            g.dead.append(d)
    if found_survivors:
        g.alive = [n for n in found_survivors if n not in g.dead]

    # Outcome narration (bullets)
    outcome_bullets = normalize_bullets(bold_character_names(outcome_raw))
    await channel.send(center_header("Outcome"))
    await stream_bullets(channel, outcome_bullets, base_delay=4.2, speed=g.current_speed)

    # Deaths/Survivors lists presentation (clean—no double bullets)
    if found_deaths:
        await channel.send(center_header("Deaths This Round"))
        await stream_bullets(channel, [f"• {bold_name(n)}" for n in found_deaths], base_delay=1.0, speed=g.current_speed)
    await channel.send(center_header("Remaining Survivors"))
    await stream_bullets(channel, [f"• {bold_name(n)}" for n in g.alive], base_delay=1.0, speed=g.current_speed)

    # End conditions + round end header (no blood emojis, centered)
    await channel.send(center_header(f"End of Round {g.round_number}"))
    g.round_number += 1

    # Save progress after each round
    safe_save_json(SAVE_FILE, g.snapshot())

    if len(g.alive) <= 1:
        await end_summary(channel, g)
        end_game()
        return

    # Next round
    if not g.terminated:
        await run_round(bot, channel, g)

# ───────────────────────────────────────────────────────────
# 🧾 End summary
# ───────────────────────────────────────────────────────────
async def end_summary(channel: discord.TextChannel, g: GameState):
    await channel.send(center_header("Game Summary"))

    deaths_list = [n for n in g.dead if n]
    if not deaths_list:
        deaths_list = ["None"]

    final_lines: List[str] = []
    top_help = get_top_or_none(g.stats["helped"])
    top_sin = get_top_or_none(g.stats["sinister"])
    top_res = get_top_or_none(g.stats["resourceful"])
    top_dig = get_top_or_none(g.stats["dignified"])

    bonds_sorted = sorted(g.stats["bonds"].items(), key=lambda x: x[1], reverse=True)
    conflicts_sorted = sorted(g.stats["conflicts"].items(), key=lambda x: x[1], reverse=True)
    best_bond = bonds_sorted[0][0] if bonds_sorted else None
    best_conflict = conflicts_sorted[0][0] if conflicts_sorted else None

    stats_bullets = []
    if top_help: stats_bullets.append(f"• 🏅 Most helpful: {bold_name(top_help)}")
    if top_res:  stats_bullets.append(f"• 🔧 Most resourceful: {bold_name(top_res)}")
    if best_bond: stats_bullets.append(f"• 🤝 Strongest bond: {bold_name(best_bond[0])} & {bold_name(best_bond[1])}")
    if best_conflict: stats_bullets.append(f"• ⚔️ Biggest opps: {bold_name(best_conflict[0])} vs {bold_name(best_conflict[1])}")
    if top_sin:  stats_bullets.append(f"• 😈 Most sinister: {bold_name(top_sin)}")
    if top_dig:  stats_bullets.append(f"• 🕊️ Most dignified: {bold_name(top_dig)}")

    await channel.send("🪦 **Deaths (most recent first)**")
    await stream_bullets(channel, [f"• {bold_name(n)}" for n in deaths_list], base_delay=0.9, speed=g.current_speed)

    if stats_bullets:
        await channel.send(center_header("Final Stats"))
        await stream_bullets(channel, stats_bullets, base_delay=1.4, speed=g.current_speed)

    if len(g.alive) == 1:
        await channel.send(f"🏆 {bold_name(g.alive[0])} is the sole survivor.")
    elif len(g.alive) == 0:
        await channel.send("💀 No survivors remain.")

# ───────────────────────────────────────────────────────────
# 🧰 Resume prompt UI
# ───────────────────────────────────────────────────────────
class ResumeView(discord.ui.View):
    def __init__(self, bot: commands.Bot, summary: str, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.result: Optional[bool] = None

    @discord.ui.button(label="Continue last save", style=discord.ButtonStyle.success)
    async def yes(self, interaction: Interaction, button: discord.ui.Button):
        self.result = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Resuming your last save…", view=self)
        self.stop()

    @discord.ui.button(label="Start new game", style=discord.ButtonStyle.danger)
    async def no(self, interaction: Interaction, button: discord.ui.Button):
        self.result = False
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Starting a new game…", view=self)
        self.stop()

# ───────────────────────────────────────────────────────────
# ⚙️ Cog
# ───────────────────────────────────────────────────────────
class ZombieGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --------------- /lizazombie + legacy ---------------
    @app_commands.command(name="lizazombie", description="Start or resume the zombie survival game")
    async def lizazombie_slash(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.channel is None or interaction.channel.id != ZOMBIE_CHANNEL_ID:
            await interaction.followup.send("❌ Use this command in the designated zombie channel.", ephemeral=True)
            return

        global active_game
        if is_active():
            await interaction.followup.send("⚠️ A game is already running.", ephemeral=True)
            return

        # Check for save
        save = safe_load_json(SAVE_FILE)
        if save:
            try:
                g = GameState.from_snapshot(save)
                brief = f"Round {g.round_number} • Alive: {', '.join(g.alive)} • Dead: {', '.join(g.dead) or 'None'}"
                view = ResumeView(self.bot, brief)
                prompt = await interaction.followup.send(
                    f"Found a previous save.\n**{brief}**\nResume it?",
                    view=view, ephemeral=True
                )
                await view.wait()
                resume = view.result is True
            except Exception:
                resume = False
        else:
            resume = False

        if resume and save:
            active_game = GameState.from_snapshot(save)
            await interaction.followup.send("Resuming game…", ephemeral=True)
        else:
            active_game = GameState(interaction.user.id)
            safe_save_json(SAVE_FILE, active_game.snapshot())
            await interaction.followup.send("New game starting…", ephemeral=True)

        # Kick off first round
        try:
            await run_round(self.bot, interaction.channel, active_game)
        except Exception as e:
            logger.error(f"run_round crashed: {e}")
            if interaction.channel:
                await interaction.channel.send("⚠️ The game crashed. Use /lizazombie to resume your last save.")

    @commands.command(name="lizazombie")
    async def lizazombie_legacy(self, ctx: commands.Context):
        if ctx.channel.id != ZOMBIE_CHANNEL_ID:
            await ctx.send("❌ Use this command in the designated zombie channel.")
            return

        # Simulate slash flow
        fake_inter = type("Fake", (), {"channel": ctx.channel})
        await self.lizazombie_slash(fake_interaction := type("X",(object,),{"channel":ctx.channel,"response":type("Y",(object,),{"defer":lambda *a,**k:None})(),"followup":type("Z",(object,),{"send":ctx.send})()})())

    # --------------- /speed + legacy ---------------
    @app_commands.command(name="speed", description="Set bullet stream speed (1.0=normal, 1.5=faster, 2.0=fastest)")
    @app_commands.describe(value="Choose 1.0 (normal), 1.5 (faster), or 2.0 (fastest)")
    @app_commands.choices(
        value=[
            app_commands.Choice(name="1.0 (normal)", value=1.0),
            app_commands.Choice(name="1.5 (faster)", value=1.5),
            app_commands.Choice(name="2.0 (fastest)", value=2.0),
        ]
    )
    async def speed_slash(self, interaction: Interaction, value: app_commands.Choice[float]):
        global active_game
        if not is_active():
            await interaction.response.send_message("⚠️ No active game. Start with /lizazombie.", ephemeral=True)
            return
        active_game.current_speed = value.value
        safe_save_json(SAVE_FILE, active_game.snapshot())
        await interaction.response.send_message(f"✅ Speed set to **{value.value}x**.", ephemeral=True)

    @commands.command(name="speed")
    async def speed_legacy(self, ctx: commands.Context, value: str = "1.0"):
        global active_game
        try:
            v = float(value)
        except Exception:
            await ctx.send("Usage: `!speed 1.0|1.5|2.0`")
            return
        if v not in ALLOWED_SPEEDS:
            await ctx.send("Speed must be 1.0, 1.5, or 2.0")
            return
        if not is_active():
            await ctx.send("⚠️ No active game. Start with /lizazombie.")
            return
        active_game.current_speed = v
        safe_save_json(SAVE_FILE, active_game.snapshot())
        await ctx.send(f"✅ Speed set to **{v}x**.")

    # --------------- /endzombie + legacy ---------------
    @app_commands.command(name="endzombie", description="End the current zombie game")
    async def endzombie_slash(self, interaction: Interaction):
        global active_game
        if not is_active():
            await interaction.response.send_message("⚠️ No active game to end.", ephemeral=True)
            return
        await interaction.response.defer()
        await end_summary(interaction.channel, active_game)
        end_game()
        await interaction.followup.send("🛑 Game ended.")

    @commands.command(name="endzombie")
    async def endzombie_legacy(self, ctx: commands.Context):
        global active_game
        if not is_active():
            await ctx.send("⚠️ No active game to end.")
            return
        await end_summary(ctx.channel, active_game)
        end_game()
        await ctx.send("🛑 Game ended.")

# ───────────────────────────────────────────────────────────
# 🧩 Cog setup (clean; no duplicate registration)
# ───────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(ZombieGame(bot))
    logger.info("✅ ZombieGame cog loaded")
