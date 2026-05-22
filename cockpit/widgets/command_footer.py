from textual.widgets import Static


class CommandFooter(Static):
    """Bottom bar showing available keyboard commands.

    commands: list of (key_label, action_label) tuples,
    e.g. [("Q", "QUIT"), ("R", "REFRESH"), ...]

    Rendered with markup disabled so literal '[' / ']' in key labels
    (e.g. the '[' / ']' lookback keys) display verbatim and cannot be
    misparsed as Rich markup tags.
    """

    def __init__(self, commands: list[tuple[str, str]], **kwargs):
        kwargs["markup"] = False
        parts = [f"[{key}]{label}" for key, label in commands]
        super().__init__("  " + "  ".join(parts), **kwargs)
