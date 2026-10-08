import unittest
from war_lan.model import Game


class Rules(unittest.TestCase):
    def game(self):
        g = Game(42)
        g.add_player("A")
        g.add_player("B")
        g.start()
        return g

    def test_map_195_connected_symmetric(self):
        g = self.game()
        self.assertEqual(len(g.countries), 195)
        seen = set()
        todo = [next(iter(g.countries))]
        while todo:
            t = todo.pop()
            if t in seen:
                continue
            seen.add(t)
            todo.extend(g.countries[t]["neighbors"])
            for n in g.countries[t]["neighbors"]:
                self.assertIn(t, g.countries[n]["neighbors"])
        self.assertEqual(len(seen), 195)
        self.assertIn("VAT", seen)
        self.assertIn("PSE", seen)

    def test_distribution(self):
        g = self.game()
        self.assertEqual(len(g.owned(0)), 98)
        self.assertEqual(len(g.owned(1)), 97)
        self.assertTrue(all(t["troops"] == 3 for t in g.board.values()))

    def test_reinforce_and_phase(self):
        g = self.game()
        t = g.owned(0)[0]
        n = g.reserve
        g.apply(0, {"op": "reinforce", "a": t, "n": n})
        self.assertEqual(g.board[t]["troops"], 3 + n)
        self.assertEqual(g.phase, "attack")
        g.apply(0, {"op": "next"})
        self.assertEqual(g.phase, "move")
        g.apply(0, {"op": "next"})
        self.assertEqual(g.turn, 1)
        self.assertEqual(g.phase, "reinforce")

    def test_reject_wrong_turn_and_bad_counts(self):
        g = self.game()
        t = g.owned(0)[0]
        for pid, n in (
            (1, 1),
            (0, 0),
            (0, -1),
            (0, True),
            (0, 1.1),
            (0, g.reserve + 1),
        ):
            with self.assertRaises(ValueError):
                g.apply(pid, {"op": "reinforce", "a": t, "n": n})
        with self.assertRaises(ValueError):
            g.apply(0, {"op": "next"})

    def attack_pair(self):
        g = self.game()
        a = "FRA"
        b = "DEU"
        g.board[a] = {"owner": 0, "troops": 4}
        g.board[b] = {"owner": 1, "troops": 2}
        g.phase = "attack"
        return g, a, b

    def test_tie_favors_defense(self):
        g, a, b = self.attack_pair()

        class Dice:
            def randint(self, a, b):
                return 4

        g.rng = Dice()
        g.apply(0, {"op": "attack", "a": a, "b": b})
        self.assertEqual(g.board[a]["troops"], 2)
        self.assertEqual(g.board[b]["troops"], 2)

    def test_capture_moves_rolled_troops(self):
        g, a, b = self.attack_pair()

        class Dice:
            def __init__(self):
                self.values = iter([6, 6, 6, 1, 1])

            def randint(self, a, b):
                return next(self.values)

        g.rng = Dice()
        g.apply(0, {"op": "attack", "a": a, "b": b})
        self.assertEqual(g.board[a], {"owner": 0, "troops": 1})
        self.assertEqual(g.board[b], {"owner": 0, "troops": 3})

    def test_nonadjacent_attack_rejected(self):
        g, a, b = self.attack_pair()
        g.board["AUS"]["owner"] = 1
        with self.assertRaises(ValueError):
            g.apply(0, {"op": "attack", "a": a, "b": "AUS"})

    def test_fortify_connected_and_once(self):
        g = self.game()
        g.phase = "move"
        for t in ("FRA", "DEU", "POL"):
            g.board[t] = {"owner": 0, "troops": 4}
        g.apply(0, {"op": "move", "a": "FRA", "b": "POL", "n": 3})
        self.assertEqual(g.board["FRA"]["troops"], 1)
        self.assertEqual(g.board["POL"]["troops"], 7)
        self.assertEqual(g.turn, 1)

    def test_region_bonus(self):
        g = self.game()
        r = g.countries["USA"]["region"]
        for t, c in g.countries.items():
            g.board[t]["owner"] = 0 if c["region"] == r else 1
        self.assertEqual(g.reinforcements(0), 5)

    def test_victory_and_private_missions(self):
        g = Game(2)
        g.add_player("A")
        g.add_player("B")
        g.start("missions")
        self.assertEqual(g.snapshot(0)["mission"], g.missions[0])
        self.assertNotIn("missions", g.snapshot(0))
        for t in g.board:
            g.board[t]["owner"] = 0
        g.check_victory(0)
        self.assertEqual(g.winner, 0)
        g = self.game()
        for i, t in enumerate(g.board):
            g.board[t]["owner"] = 0 if i < 156 else 1
        g.check_victory(0)
        self.assertEqual(g.winner, 0)

    def test_disconnect_pause(self):
        g = self.game()
        g.phase = "paused"
        with self.assertRaises(ValueError):
            g.apply(0, {"op": "next"})


if __name__ == "__main__":
    unittest.main()
