"""Pure game rules. Only the host mutates this state."""

import json
import random
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parent / "assets/world.json"


def load_map():
    return json.loads(MAP_PATH.read_text(encoding="utf8"))


class Game:
    def __init__(self, seed=None):
        self.map = load_map()
        self.countries = {c["id"]: c for c in self.map["countries"]}
        self.rng = random.Random(seed)
        self.players = []
        self.started = False
        self.winner = None
        self.log = "Aguardando jogadores."
        self.turn = 0
        self.phase = "lobby"
        self.reserve = 0
        self.board = {}
        self.mode = "domination"
        self.missions = {}

    def add_player(self, name):
        if self.started or len(self.players) >= 6:
            raise ValueError("Lobby fechado ou cheio.")
        pid = len(self.players)
        self.players.append({"id": pid, "name": str(name).strip()[:24] or "Jogador"})
        return pid

    def start(self, mode="domination"):
        if self.started or len(self.players) < 2:
            raise ValueError("São necessários 2 a 6 jogadores.")
        if mode not in ("domination", "missions"):
            raise ValueError("Modo inválido.")
        self.mode = mode
        territories = list(self.countries)
        self.rng.shuffle(territories)
        self.board = {
            t: {"owner": i % len(self.players), "troops": 3}
            for i, t in enumerate(territories)
        }
        regions = sorted({c["region"] for c in self.countries.values()})
        for p in self.players:
            self.missions[p["id"]] = {
                "regions": self.rng.sample(regions, 2),
                "minimum": 60,
            }
        self.started = True
        self.phase = "reinforce"
        self.reserve = self.reinforcements(0)
        self.log = "Partida iniciada. Distribua seus reforços."

    def owned(self, pid):
        return [t for t, v in self.board.items() if v["owner"] == pid]

    def reinforcements(self, pid):
        owned = set(self.owned(pid))
        bonus = 0
        for region in {c["region"] for c in self.countries.values()}:
            ts = {t for t, c in self.countries.items() if c["region"] == region}
            if ts <= owned:
                bonus += max(2, len(ts) // 5)
        return max(3, len(owned) // 3) + bonus

    def connected(self, a, b, pid):
        seen = {a}
        todo = [a]
        while todo:
            for n in self.countries[todo.pop()]["neighbors"]:
                if n not in seen and self.board[n]["owner"] == pid:
                    seen.add(n)
                    todo.append(n)
        return b in seen

    def apply(self, pid, cmd):
        if not self.started or self.winner is not None:
            raise ValueError("Partida não está ativa.")
        if self.phase == "paused":
            raise ValueError("Partida pausada após desconexão.")
        if pid != self.turn:
            raise ValueError("Não é seu turno.")
        op = cmd.get("op")
        a = cmd.get("a")
        b = cmd.get("b")
        n = cmd.get("n", 1)
        if type(n) is not int or n < 1 or n > 100000:
            raise ValueError("Quantidade inválida.")
        if op in ("reinforce", "attack", "move"):
            if a not in self.board or self.board[a]["owner"] != pid:
                raise ValueError("Origem inválida.")
        if op == "reinforce":
            if self.phase != "reinforce" or n > self.reserve:
                raise ValueError("Reforço inválido.")
            self.board[a]["troops"] += n
            self.reserve -= n
            if self.reserve == 0:
                self.phase = "attack"
        elif op == "attack":
            if (
                self.phase != "attack"
                or b not in self.countries[a]["neighbors"]
                or self.board[b]["owner"] == pid
            ):
                raise ValueError("Ataque inválido.")
            src, dst = self.board[a], self.board[b]
            if src["troops"] < 2:
                raise ValueError("Mantenha uma tropa na origem.")
            dice = min(3, src["troops"] - 1)
            atk = sorted((self.rng.randint(1, 6) for _ in range(dice)), reverse=True)
            defense = sorted(
                (self.rng.randint(1, 6) for _ in range(min(2, dst["troops"]))),
                reverse=True,
            )
            for x, y in zip(atk, defense):
                if x > y:
                    dst["troops"] -= 1
                else:
                    src["troops"] -= 1
            if dst["troops"] == 0:
                moved = min(dice, src["troops"] - 1)
                src["troops"] -= moved
                dst.update(owner=pid, troops=moved)
            self.log = f"Dados: {atk} × {defense} (empate favorece defesa)."
        elif op == "move":
            if (
                self.phase != "move"
                or b not in self.board
                or a == b
                or self.board[b]["owner"] != pid
                or not self.connected(a, b, pid)
                or n >= self.board[a]["troops"]
            ):
                raise ValueError("Movimentação inválida.")
            self.board[a]["troops"] -= n
            self.board[b]["troops"] += n
            self.end_turn()
        elif op == "next":
            if self.phase == "reinforce":
                raise ValueError("Distribua todos os reforços.")
            if self.phase == "attack":
                self.phase = "move"
            else:
                self.end_turn()
        else:
            raise ValueError("Comando desconhecido.")
        self.check_victory(pid)

    def end_turn(self):
        self.turn = (self.turn + 1) % len(self.players)
        while not self.owned(self.turn):
            self.turn = (self.turn + 1) % len(self.players)
        self.phase = "reinforce"
        self.reserve = self.reinforcements(self.turn)

    def check_victory(self, pid):
        owned = set(self.owned(pid))
        won = len(owned) >= 156  # 80% of 195
        if self.mode == "missions":
            mission = self.missions[pid]
            target = {
                t
                for t, c in self.countries.items()
                if c["region"] in mission["regions"]
            }
            won = len(owned) >= mission["minimum"] and target <= owned
        if won:
            self.winner = pid
            self.log = f"Vitória de {self.players[pid]['name']}!"

    def snapshot(self, pid):
        return {
            "players": self.players,
            "started": self.started,
            "board": self.board,
            "turn": self.turn,
            "phase": self.phase,
            "reserve": self.reserve,
            "winner": self.winner,
            "log": self.log,
            "mode": self.mode,
            "mission": self.missions.get(pid) if self.mode == "missions" else None,
        }
