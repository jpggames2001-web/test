import queue
import socket
import time
import unittest
from war_lan.network import Client, Host, Discovery, encode, frames, PROTOCOL


def wait(client, kind, predicate=lambda m: True):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        try:
            msg = client.events.get(timeout=0.1)
        except queue.Empty:
            continue
        if msg["type"] == kind and predicate(msg):
            return msg
    raise AssertionError("Não recebeu " + kind)


class Network(unittest.TestCase):
    def test_tcp_host_two_clients_authority_and_privacy(self):
        host = Host(port=0, discovery_port=47779)
        a = b = None
        try:
            a = Client("127.0.0.1", host.port, "Ana", host_key=host.owner_key)
            self.assertEqual(wait(a, "welcome")["id"], 0)
            b = Client("127.0.0.1", host.port, "Beto")
            self.assertEqual(wait(b, "welcome")["id"], 1)
            b.send({"op": "start"})
            wait(b, "error")
            a.send({"op": "start", "mode": "missions"})
            sa = wait(a, "state", lambda m: m["state"]["started"])["state"]
            sb = wait(b, "state", lambda m: m["state"]["started"])["state"]
            self.assertNotIn("missions", sa)
            self.assertNotIn("missions", sb)
            self.assertEqual(len(sa["board"]), 195)
            time.sleep(0.05)
            b.send({"op": "next"})
            self.assertIn("turno", wait(b, "error")["message"])
            origin = next(t for t, v in sa["board"].items() if v["owner"] == 0)
            a.send({"op": "reinforce", "a": origin, "n": sa["reserve"]})
            result = wait(b, "state", lambda m: m["state"]["phase"] == "attack")[
                "state"
            ]
            self.assertEqual(result["board"][origin]["troops"], 3 + sa["reserve"])
            b.close()
            wait(a, "state", lambda m: m["state"]["phase"] == "paused")
        finally:
            if a:
                a.close()
            if b:
                b.close()
            host.close()

    def test_creator_is_not_first_remote_peer(self):
        host = Host(port=0, discovery_port=47779)
        remote = creator = None
        try:
            remote = Client("127.0.0.1", host.port, "Remoto")
            self.assertEqual(wait(remote, "welcome")["id"], 0)
            remote.send({"op": "start"})
            self.assertIn("criador", wait(remote, "error")["message"])
            creator = Client("127.0.0.1", host.port, "Criador", host_key=host.owner_key)
            self.assertEqual(wait(creator, "welcome")["id"], 1)
            creator.send({"op": "start"})
            state = wait(remote, "state", lambda m: m["state"]["started"])["state"]
            self.assertEqual(state["host"], 1)
        finally:
            if remote:
                remote.close()
            if creator:
                creator.close()
            host.close()

    def test_udp_discovery_expiry(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("", 0))
            port = probe.getsockname()[1]
        d = Discovery(port)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                udp.sendto(
                    encode(
                        {
                            "protocol": PROTOCOL,
                            "kind": "lobby",
                            "name": "Teste",
                            "port": 47777,
                            "players": 2,
                        }
                    ),
                    ("127.0.0.1", port),
                )
            deadline = time.monotonic() + 2
            while not d.available() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(d.available()[0]["name"], "Teste")
            with d.lock:
                for g in d.games.values():
                    g["time"] -= 5
            self.assertFalse(d.available())
        finally:
            d.close()

    def test_udp_actual_broadcast(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("", 0))
            port = probe.getsockname()[1]
        d = Discovery(port)
        h = Host(port=0, discovery_port=port)
        try:
            deadline = time.monotonic() + 3
            while not d.available() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(d.available(), "Broadcast não chegou ao listener local")
            self.assertEqual(d.available()[0]["port"], h.port)
        finally:
            h.close()
            d.close()

    def test_frame_bounds_and_fragmentation(self):
        a, b = socket.socketpair()
        try:
            a.sendall(b'{"op":')
            a.sendall(b'"next"}\n')
            self.assertEqual(next(frames(b)), {"op": "next"})
            a.sendall(b"[]\n")
            with self.assertRaises(ValueError):
                next(frames(b))
            a.sendall(b"x" * 65537 + b"\n")
            with self.assertRaises(ValueError):
                next(frames(b))
        finally:
            a.close()
            b.close()


if __name__ == "__main__":
    unittest.main()
