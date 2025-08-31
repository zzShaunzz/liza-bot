import random

CHARACTERS = [
    "Shaun Sadsarin", "Addison Sadsarin", "Kate Nainggolan", "Jill Nainggolan", "Noah Nainggolan",
    "Dylan Pastorin", "Gabe Muy", "Vivian Muy", "Aiden Muy", "Ella Muy", "Nico Muy", "Jordan"
]

class GameState:
    def __init__(self, initiator):
        self.initiator = initiator
        self.round = 0
        self.alive = CHARACTERS.copy()
        self.dead = []
        self.relationships = {}  # e.g., ("Shaun", "Addy"): 10
        self.resources = {"food": 5, "tools": 3}
        self.health = {name: 100 for name in CHARACTERS}
        self.stats = {
            "helpful": {},
            "sinister": {},
            "resourceful": {},
            "bonds": {},
            "conflicts": {},
            "dignified": {}
        }
        self.last_choice = None
        self.last_events = ""
        self.votes = {}
        self.options = []

active_game = None

def start_game(user_id):
    global active_game
    active_game = GameState(user_id)

def end_game():
    global active_game
    active_game = None

def is_active():
    return active_game is not None
