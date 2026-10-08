import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import argparse
import unittest
import pygame
from war_lan.ui import App
from war_lan.model import Game


class Renderer(unittest.TestCase):
    def test_menu_lobby_map_and_event_loop(self):
        app = App(argparse.Namespace(port=47777, discovery_port=47780))
        try:
            app.menu()
            g = Game(42)
            g.add_player("Ana")
            g.add_player("Beto")
            app.pid = 0
            app.state = g.snapshot(0)
            app.lobby()
            g.start()
            app.state = g.snapshot(0)
            app.selected = "BRA"
            app.game()
            cached = app._map_surface
            app.game()
            self.assertIs(app._map_surface, cached)
            app.state["board"]["BRA"]["owner"] = 1 - app.state["board"]["BRA"]["owner"]
            app.game()
            self.assertIsNot(app._map_surface, cached)
            app.zoom = 3
            app.game()
            self.assertEqual(
                app.hit(app.project(*app.countries["BRA"]["center"])), "BRA"
            )
            self.assertNotEqual(app.screen.get_at((500, 400))[:3], (0, 0, 0))
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            app.run()
        finally:
            if app.discovery:
                app.discovery.close()
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
