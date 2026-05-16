"""Entry point for the cockpit TUI.

Usage:
    python -m scripts.cockpit
"""
from cockpit.app import CockpitApp


def main():
    app = CockpitApp()
    app.run()


if __name__ == "__main__":
    main()
