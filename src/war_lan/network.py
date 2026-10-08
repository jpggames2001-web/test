"""UDP discovery and length-bounded JSON-lines over authoritative TCP.

All mutations run under one host lock. Clients send intentions, never dice or
board state. This protocol is designed for trusted LANs, without encryption.
"""

import json
import queue
import secrets
import socket
import threading
import time
from .model import Game

DISCOVERY_PORT = 47778
GAME_PORT = 47777
MAX_FRAME = 65536
PROTOCOL = "war-lan/1"


def encode(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf8"
    )


def frames(sock):
    buf = b""
    while True:
        try:
            data = sock.recv(8192)
        except socket.timeout:
            continue
        if not data:
            return
        buf += data
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if len(line) > MAX_FRAME:
                raise ValueError("Mensagem muito grande.")
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError("Mensagem inválida.")
            yield obj
        if len(buf) > MAX_FRAME:
            raise ValueError("Mensagem muito grande.")


class Discovery:
    def __init__(self, port=DISCOVERY_PORT):
        self.port = port
        self.games = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.error = ""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("", port))
        except OSError:
            self.sock.close()
            raise
        self.sock.settimeout(0.5)
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        while not self.stop.is_set():
            try:
                data, (ip, _) = self.sock.recvfrom(4096)
                msg = json.loads(data)
                if (
                    isinstance(msg, dict)
                    and msg.get("protocol") == PROTOCOL
                    and msg.get("kind") == "lobby"
                ):
                    port = msg.get("port")
                    if type(port) is int and 1 <= port <= 65535:
                        with self.lock:
                            self.games[(ip, port)] = {
                                "ip": ip,
                                "port": port,
                                "name": str(msg.get("name", "LAN"))[:48],
                                "players": msg.get("players", 0),
                                "time": time.monotonic(),
                            }
            except socket.timeout:
                pass
            except (OSError, ValueError, UnicodeError, RecursionError):
                pass

    def available(self):
        with self.lock:
            return [
                dict(g) for g in self.games.values() if time.monotonic() - g["time"] < 4
            ]

    def close(self):
        self.stop.set()
        self.sock.close()


class Host:
    def __init__(self, name="War LAN", port=GAME_PORT, discovery_port=DISCOVERY_PORT):
        self.name = name
        self.discovery_port = discovery_port
        self.game = Game()
        self.lock = threading.RLock()
        self.owner_key = secrets.token_hex(16)
        self.owner_id = None
        self.clients = {}
        self.send_locks = {}
        self.active = set()
        self.stop = threading.Event()
        self.slots = threading.BoundedSemaphore(16)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("", port))
            self.sock.listen(8)
        except OSError:
            self.sock.close()
            raise
        self.port = self.sock.getsockname()[1]
        self.sock.settimeout(0.5)
        threading.Thread(target=self._accept, daemon=True).start()
        threading.Thread(target=self._announce, daemon=True).start()

    def _announce(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while not self.stop.is_set():
                with self.lock:
                    msg = {
                        "protocol": PROTOCOL,
                        "kind": "lobby",
                        "name": self.name,
                        "port": self.port,
                        "players": len(self.active),
                    }
                    advertise = not self.game.started
                if advertise:
                    try:
                        udp.sendto(
                            encode(msg), ("255.255.255.255", self.discovery_port)
                        )
                    except OSError:
                        pass
                self.stop.wait(1)

    def _accept(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            if not self.slots.acquire(blocking=False):
                conn.close()
                continue
            conn.settimeout(3)
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _send(self, pid, msg):
        with self.send_locks[pid]:
            self.clients[pid].sendall(encode(msg))

    def _broadcast(self):
        for pid in list(self.active):
            try:
                state = self.game.snapshot(pid)
                state["host"] = self.owner_id
                self._send(pid, {"type": "state", "state": state})
            except OSError:
                try:
                    self.clients[pid].shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def _serve(self, conn):
        pid = None
        try:
            # Handshake uses a strict read deadline before switching to the
            # timeout-tolerant stream used during idle game turns.
            line = b""
            deadline = time.monotonic() + 3
            while b"\n" not in line:
                if time.monotonic() > deadline:
                    raise ValueError("Handshake expirado.")
                chunk = conn.recv(1)
                if not chunk:
                    raise ValueError("Conexão encerrada.")
                line += chunk
                if len(line) > 1024:
                    raise ValueError("Handshake muito grande.")
            hello = json.loads(line)
            if not isinstance(hello, dict):
                raise ValueError("Handshake inválido.")
            stream = frames(conn)
            if hello.get("op") != "hello" or hello.get("protocol") != PROTOCOL:
                raise ValueError("Protocolo incompatível.")
            with self.lock:
                pid = self.game.add_player(hello.get("name", "Jogador"))
                self.clients[pid] = conn
                self.send_locks[pid] = threading.Lock()
                self.active.add(pid)
                if hello.get("host_key") == self.owner_key and self.owner_id is None:
                    self.owner_id = pid
                self._send(pid, {"type": "welcome", "id": pid})
                self._broadcast()
            # Idle reads retry timeouts; writes remain bounded so a stalled
            # peer cannot block the host's transaction lock indefinitely.
            conn.settimeout(1)
            last = 0.0
            for cmd in stream:
                now = time.monotonic()
                if now - last < 0.04:
                    continue
                last = now
                with self.lock:
                    try:
                        if cmd.get("op") == "start":
                            if pid != self.owner_id:
                                raise ValueError("Só o criador pode iniciar.")
                            if len(self.active) != len(self.game.players):
                                raise ValueError("Um jogador saiu. Reabra o lobby.")
                            self.game.start(cmd.get("mode", "domination"))
                        else:
                            self.game.apply(pid, cmd)
                        self._broadcast()
                    except (ValueError, TypeError, KeyError) as exc:
                        self._send(pid, {"type": "error", "message": str(exc)})
        except (OSError, ValueError, UnicodeError, RecursionError, StopIteration):
            pass
        finally:
            with self.lock:
                if pid is not None:
                    self.active.discard(pid)
                    self.game.log = "Jogador desconectado. Encerre e reabra a partida; reconexão não é suportada."
                    if self.game.started:
                        self.game.phase = "paused"
                    self._broadcast()
            conn.close()
            self.slots.release()

    def close(self):
        self.stop.set()
        self.sock.close()
        # Closing sockets wakes receiver threads without joining under the lock.
        for conn in list(self.clients.values()):
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()


class Client:
    def __init__(self, ip, port, name, host_key=None):
        self.sock = socket.create_connection((ip, port), timeout=3)
        self.sock.settimeout(None)
        self.events = queue.Queue(maxsize=128)
        self.lock = threading.Lock()
        self.closed = False
        self.send(
            {"op": "hello", "protocol": PROTOCOL, "name": name, "host_key": host_key}
        )
        threading.Thread(target=self._receive, daemon=True).start()

    def _receive(self):
        try:
            for msg in frames(self.sock):
                self.events.put_nowait(msg)
        except (OSError, ValueError, UnicodeError, RecursionError, queue.Full):
            pass
        finally:
            try:
                self.events.put_nowait({"type": "disconnected"})
            except queue.Full:
                pass

    def send(self, cmd):
        with self.lock:
            self.sock.sendall(encode(cmd))

    def close(self):
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
