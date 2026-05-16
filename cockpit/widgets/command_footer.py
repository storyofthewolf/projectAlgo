from textual.widgets import Static


class CommandFooter(Static):
    """Bottom bar showing available keyboard commands.

    commands: list of (key_label, action_label) tuples,
    e.g. [("Q", "QUIT"), ("R", "REFRESH"), ...]
    """

    def __init__(self, commands: list[tuple[str, str]], **kwargs):
        parts = []
        for key, label in commands:
            parts.append(f"[{key}]{label}")
        super().__init__("  " + "  ".join(parts), **kwargs)
