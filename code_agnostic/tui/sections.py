from rich.panel import Panel

from code_agnostic.tui.enums import UIStyle


class UISection:
    @staticmethod
    def wrap(
        title: str, body, style: str = UIStyle.BLUE.value, subtitle: str | None = None
    ) -> Panel:
        return Panel(
            body, title=title, subtitle=subtitle, border_style=style, padding=(0, 1)
        )

    @staticmethod
    def note(title: str, body: str, style: str) -> Panel:
        return Panel(body, title=title, border_style=style, padding=(0, 1))
