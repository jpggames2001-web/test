"""Pygame menus and vector-map renderer; network events stay off render thread."""

import argparse
import queue
import pygame
from .model import load_map
from .network import Client, Discovery, Host, GAME_PORT, DISCOVERY_PORT

COLORS = [
    (222, 80, 85),
    (72, 146, 231),
    (68, 188, 114),
    (225, 178, 54),
    (166, 105, 218),
    (49, 192, 192),
]
BG = (19, 26, 38)
PANEL = (29, 40, 57)
WHITE = (228, 235, 243)


class App:
    def __init__(self, args):
        pygame.init()
        self.screen = pygame.display.set_mode((1280, 800), pygame.RESIZABLE)
        pygame.display.set_caption("War LAN — Estratégia global")
        self.font = pygame.font.SysFont("dejavusans", 16)
        self.small = pygame.font.SysFont("dejavusans", 12)
        self.clock = pygame.time.Clock()
        self.running = True
        self.args = args
        self.world = load_map()
        self.countries = {c["id"]: c for c in self.world["countries"]}
        self.host = None
        self.client = None
        self.pid = None
        self.state = None
        self.error = ""
        self.discovery = None
        try:
            self.discovery = Discovery(args.discovery_port)
        except OSError as exc:
            self.error = f"Descoberta indisponível: {exc}; use IP direto."
        self.name = "Jogador"
        self.address = f"127.0.0.1:{args.port}"
        self.focus = "name"
        self.buttons = []
        self._map_key = None
        self._map_surface = None
        self._hit_key = None
        self._hit_value = None
        self._rings = {}
        for t, c in self.countries.items():
            self._rings[t] = []
            for ring in self.polygons(c):
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                self._rings[t].append((ring, (min(xs), min(ys), max(xs), max(ys))))
        self.zoom = 1.0
        self.pan = [0, 0]
        self.drag = False
        self.selected = None
        self.target = None
        self.amount = "1"
        self.mode = "domination"

    def text(self, value, pos, color=WHITE, small=False):
        self.screen.blit(
            (self.small if small else self.font).render(str(value), True, color), pos
        )

    def button(self, label, rect, action):
        r = pygame.Rect(rect)
        pygame.draw.rect(self.screen, (47, 68, 93), r, border_radius=5)
        self.text(label, (r.x + 10, r.y + 8))
        self.buttons.append((r, action))

    def connect(self, ip, port):
        try:
            self.client = Client(
                ip, port, self.name, host_key=self.host.owner_key if self.host else None
            )
            self.error = ""
            self.focus = None
        except (OSError, ValueError) as exc:
            self.error = f"Falha na conexão: {exc}"

    def create(self):
        try:
            self.host = Host(
                f"Partida de {self.name}", self.args.port, self.args.discovery_port
            )
            self.connect("127.0.0.1", self.host.port)
            if self.client is None:
                self.host.close()
                self.host = None
        except OSError as exc:
            self.error = f"Não foi possível abrir LAN: {exc}"

    def direct(self):
        try:
            ip, sep, port = self.address.partition(":")
            self.connect(ip, int(port) if sep else self.args.port)
        except ValueError:
            self.error = "Use IPv4:porta."

    def send(self, cmd):
        try:
            self.client.send(cmd)
        except OSError as exc:
            self.error = f"Conexão perdida: {exc}"

    def leave(self):
        if self.client:
            self.client.close()
        if self.host:
            self.host.close()
        self.client = self.host = self.state = self.pid = None
        self.selected = self.target = None

    def events(self):
        if not self.client:
            return
        while True:
            try:
                msg = self.client.events.get_nowait()
            except queue.Empty:
                break
            if msg["type"] == "welcome":
                self.pid = msg["id"]
            elif msg["type"] == "state":
                self.state = msg["state"]
            elif msg["type"] == "error":
                self.error = msg["message"]
            elif msg["type"] == "disconnected":
                self.error = "Conexão encerrada. Use Sair para voltar ao menu."

    def menu(self):
        self.text("WAR LAN — 195 países / 2 a 6 jogadores", (40, 32))
        self.text(
            "Nome: " + self.name + (" |" if self.focus == "name" else ""), (40, 88)
        )
        self.button(
            "Editar nome", (40, 120, 190, 40), lambda: setattr(self, "focus", "name")
        )
        self.button("Criar partida LAN", (250, 120, 240, 40), self.create)
        self.text(
            "Conexão direta: "
            + self.address
            + (" |" if self.focus == "address" else ""),
            (40, 186),
        )
        self.button(
            "Editar IPv4:porta",
            (40, 220, 190, 40),
            lambda: setattr(self, "focus", "address"),
        )
        self.button("Conectar", (250, 220, 240, 40), self.direct)
        self.text("Jogos LAN disponíveis (anúncios expiram em 4 segundos)", (40, 305))
        for i, g in enumerate(self.discovery.available() if self.discovery else []):
            self.button(
                f"{g['name']} — {g['ip']}:{g['port']} ({g['players']}/6)",
                (40, 345 + i * 48, 680, 40),
                lambda g=g: self.connect(g["ip"], g["port"]),
            )
        self.text(
            "Firewall: TCP "
            + str(self.args.port)
            + " e UDP "
            + str(self.args.discovery_port)
            + ". Mesma rede, sem isolamento Wi-Fi.",
            (40, self.screen.get_height() - 70),
            small=True,
        )

    def lobby(self):
        self.text("Lobby LAN", (40, 30))
        for i, p in enumerate(self.state["players"]):
            self.text(p["name"], (40, 90 + i * 38), COLORS[p["id"]])
        self.text(
            "Modo: "
            + (
                "Missões secretas"
                if self.mode == "missions"
                else "Dominação: 80% do mapa"
            ),
            (40, 350),
        )
        if self.pid == self.state.get("host", 0):
            self.button(
                "Alternar modo",
                (40, 390, 210, 40),
                lambda: setattr(
                    self,
                    "mode",
                    "missions" if self.mode == "domination" else "domination",
                ),
            )
            self.button(
                "Iniciar partida",
                (270, 390, 210, 40),
                lambda: self.send({"op": "start", "mode": self.mode}),
            )
        else:
            self.text("O criador inicia a partida.", (40, 410))
        self.button("Sair", (40, 455, 210, 40), self.leave)

    def viewport(self):
        return pygame.Rect(
            0,
            60,
            max(360, self.screen.get_width() - 330),
            self.screen.get_height() - 105,
        )

    def project(self, lon, lat):
        v = self.viewport()
        scale = min(v.w / 360, v.h / 180) * self.zoom
        return (
            v.centerx + lon * scale + self.pan[0],
            v.centery - lat * scale + self.pan[1],
        )

    def polygons(self, c):
        g = c["geometry"]
        if not g:
            return []
        return (
            [p[0] for p in g["coordinates"]]
            if g["type"] == "MultiPolygon"
            else [g["coordinates"][0]]
        )

    def hit(self, pos):
        key = (tuple(pos), self.zoom, tuple(self.pan), tuple(self.screen.get_size()))
        if key != self._hit_key:
            self._hit_key = key
            self._hit_value = self._hit_uncached(pos)
        return self._hit_value

    def _hit_uncached(self, pos):
        # Markers cover microstates and islands too; nearest marker takes priority.
        candidates = []
        for t, c in self.countries.items():
            x, y = self.project(*c["center"])
            d = (x - pos[0]) ** 2 + (y - pos[1]) ** 2
            if d < 100:
                candidates.append((d, t))
        if candidates:
            return min(candidates)[1]
        for t, c in sorted(
            self.countries.items(), key=lambda item: item[1].get("area", 0)
        ):
            for ring in self.polygons(c):
                points = [self.project(*p[:2]) for p in ring]
                inside = False
                j = len(points) - 1
                for i, (x, y) in enumerate(points):
                    xj, yj = points[j]
                    if (y > pos[1]) != (yj > pos[1]) and pos[0] < (xj - x) * (
                        pos[1] - y
                    ) / (yj - y) + x:
                        inside = not inside
                    j = i
                if inside:
                    return t
        return None

    def action(self):
        try:
            n = int(self.amount)
        except ValueError:
            self.error = "Informe uma quantidade inteira."
            return
        if not self.selected:
            self.error = "Selecione a origem."
            return
        if self.state["phase"] not in ("reinforce", "attack", "move"):
            self.error = "Partida pausada ou encerrada."
            return
        op = {"reinforce": "reinforce", "attack": "attack", "move": "move"}[
            self.state["phase"]
        ]
        self.send({"op": op, "a": self.selected, "b": self.target, "n": n})

    def game(self):
        state = self.state
        v = self.viewport()
        self.screen.set_clip(v)
        key = (
            self.screen.get_size(),
            self.zoom,
            tuple(self.pan),
            tuple((t, b["owner"]) for t, b in state["board"].items()),
        )
        if key != self._map_key:
            self._map_key = key
            self._map_surface = pygame.Surface(self.screen.get_size())
            self._map_surface.fill(BG)
            self._map_surface.set_clip(v)
            scale = min(v.w / 360, v.h / 180) * self.zoom
            for t, c in sorted(
                self.countries.items(),
                key=lambda item: item[1].get("area", 0),
                reverse=True,
            ):
                color = COLORS[state["board"][t]["owner"]]
                for ring, (left, bottom, right, top) in self._rings[t]:
                    # Cull off-screen and subpixel islands before projection.
                    if (right - left) * (top - bottom) * scale * scale < 0.6:
                        continue
                    x1, y1 = self.project(left, top)
                    x2, y2 = self.project(right, bottom)
                    if x2 < v.left or x1 > v.right or y2 < v.top or y1 > v.bottom:
                        continue
                    points = [self.project(*p[:2]) for p in ring]
                    if len(points) > 2:
                        pygame.draw.polygon(self._map_surface, color, points)
                        pygame.draw.lines(self._map_surface, BG, True, points, 1)
        self.screen.blit(self._map_surface, (0, 0))
        if self.selected:
            for n in self.countries[self.selected]["neighbors"]:
                pygame.draw.line(
                    self.screen,
                    (215, 220, 160),
                    self.project(*self.countries[self.selected]["center"]),
                    self.project(*self.countries[n]["center"]),
                    1,
                )
        for t, c in self.countries.items():
            x, y = self.project(*c["center"])
            if not v.collidepoint(x, y):
                continue
            color = COLORS[state["board"][t]["owner"]]
            pygame.draw.circle(self.screen, BG, (int(x), int(y)), 8)
            pygame.draw.circle(self.screen, color, (int(x), int(y)), 6)
            if t in (self.selected, self.target):
                pygame.draw.circle(self.screen, WHITE, (int(x), int(y)), 11, 2)
            if self.zoom >= 2.3 or t in (self.selected, self.target):
                self.text(
                    c["name"] + ": " + str(state["board"][t]["troops"]),
                    (x + 9, y - 8),
                    small=True,
                )
        self.screen.set_clip(None)
        x = v.right + 12
        pygame.draw.rect(
            self.screen, PANEL, (v.right, 60, 330, self.screen.get_height() - 60)
        )
        p = state["players"][state["turn"]]
        self.text("Vez de " + p["name"], (x, 80), COLORS[p["id"]])
        self.text(
            "Fase: "
            + {
                "reinforce": "Reforço",
                "attack": "Ataque",
                "move": "Movimentação",
                "paused": "Pausada",
            }[state["phase"]],
            (x, 110),
        )
        self.text("Reforços: " + str(state["reserve"]), (x, 140))
        for i, (label, t) in enumerate(
            (("Origem", self.selected), ("Destino", self.target))
        ):
            self.text(
                label + ": " + (self.countries[t]["name"] if t else "—"),
                (x, 180 + i * 60),
                small=True,
            )
            if t:
                self.text(
                    "Tropas: " + str(state["board"][t]["troops"]),
                    (x, 202 + i * 60),
                    small=True,
                )
        self.text(
            "Quantidade: " + self.amount + (" |" if self.focus == "amount" else ""),
            (x, 310),
        )
        self.button(
            "Editar quantidade",
            (x, 340, 300, 38),
            lambda: setattr(self, "focus", "amount"),
        )
        if state["winner"] is None and state["phase"] != "paused":
            self.button("Aplicar ação", (x, 390, 300, 38), self.action)
            self.button(
                "Avançar fase / encerrar",
                (x, 440, 300, 38),
                lambda: self.send({"op": "next"}),
            )
        elif state["winner"] is not None:
            self.text(
                "Vencedor: " + state["players"][state["winner"]]["name"], (x, 395)
            )
        else:
            self.text("Partida pausada: jogador saiu.", (x, 395))
        self.button("Sair", (x, 490, 300, 38), self.leave)
        self.text("Clique: origem; Shift+clique: destino", (x, 550), small=True)
        self.text("Roda: zoom; botão direito: arrastar", (x, 573), small=True)
        self.text("Enter: ação; Esc: parar edição", (x, 596), small=True)
        if state.get("mission"):
            self.text("Sua missão: 60 países e dominar", (x, 635), small=True)
            for i, r in enumerate(state["mission"]["regions"]):
                self.text(r, (x, 657 + i * 20), small=True)
        for i, player in enumerate(state["players"]):
            self.text(
                player["name"][:14], (10 + i * 145, 5), COLORS[player["id"]], small=True
            )
        self.text(state["log"], (10, 24), small=True)
        self.text(
            "80% = 156 países. Cor indica dono. Nomes e tropas aparecem com zoom.",
            (10, self.screen.get_height() - 40),
            small=True,
        )

    def run(self):
        try:
            while self.running:
                self.events()
                self.buttons = []
                self.screen.fill(BG)
                if not self.client:
                    self.menu()
                elif not self.state:
                    self.text("Conectando…", (40, 40))
                    self.button("Sair", (40, 100, 210, 40), self.leave)
                elif not self.state["started"]:
                    self.lobby()
                else:
                    self.game()
                if self.error:
                    self.text(
                        self.error[:145],
                        (10, self.screen.get_height() - 22),
                        (255, 155, 120),
                        small=True,
                    )
                if (
                    self.state
                    and self.state["started"]
                    and self.viewport().collidepoint(pygame.mouse.get_pos())
                ):
                    hovered = self.hit(pygame.mouse.get_pos())
                    if hovered:
                        c = self.countries[hovered]
                        b = self.state["board"][hovered]
                        self.text(
                            c["name"]
                            + " | "
                            + self.state["players"][b["owner"]]["name"]
                            + " | "
                            + str(b["troops"])
                            + " tropas",
                            (12, 43),
                            small=True,
                        )
                pygame.display.flip()
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        self.running = False
                    elif e.type == pygame.MOUSEBUTTONDOWN:
                        if e.button == 1:
                            handled = False
                            for rect, fn in self.buttons:
                                if rect.collidepoint(e.pos):
                                    fn()
                                    handled = True
                                    break
                            if (
                                not handled
                                and self.state
                                and self.state["started"]
                                and self.viewport().collidepoint(e.pos)
                            ):
                                t = self.hit(e.pos)
                                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                                    self.target = t
                                else:
                                    self.selected = t
                        elif e.button == 3:
                            self.drag = True
                    elif e.type == pygame.MOUSEBUTTONUP and e.button == 3:
                        self.drag = False
                    elif e.type == pygame.MOUSEMOTION and self.drag:
                        self.pan[0] += e.rel[0]
                        self.pan[1] += e.rel[1]
                    elif (
                        e.type == pygame.MOUSEWHEEL
                        and self.state
                        and self.state["started"]
                    ):
                        old = self.zoom
                        self.zoom = max(0.6, min(15, self.zoom * 1.15**e.y))
                        mx, my = pygame.mouse.get_pos()
                        v = self.viewport()
                        factor = self.zoom / old
                        self.pan = [
                            mx - v.centerx - (mx - v.centerx - self.pan[0]) * factor,
                            my - v.centery - (my - v.centery - self.pan[1]) * factor,
                        ]
                    elif e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_ESCAPE:
                            self.focus = None
                        elif e.key == pygame.K_RETURN:
                            if self.state and self.state["started"]:
                                self.action()
                            elif not self.client and self.focus == "address":
                                self.direct()
                            self.focus = None
                        elif e.key == pygame.K_BACKSPACE and self.focus:
                            setattr(self, self.focus, getattr(self, self.focus)[:-1])
                        elif self.focus and e.unicode.isprintable():
                            value = getattr(self, self.focus)
                            if len(value) < 48 and (
                                self.focus != "amount" or e.unicode.isdigit()
                            ):
                                setattr(self, self.focus, value + e.unicode)
                self.clock.tick(60)
        finally:
            self.leave()
            if self.discovery:
                self.discovery.close()
            pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="War LAN")
    parser.add_argument("--port", type=int, default=GAME_PORT)
    parser.add_argument("--discovery-port", type=int, default=DISCOVERY_PORT)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.discovery_port <= 65535:
        parser.error("Portas devem estar entre 1 e 65535.")
    App(args).run()
