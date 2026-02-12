from enum import Enum

from code_agnostic.models import ActionStatus


class UIStyle(str, Enum):
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    CYAN = "cyan"
    MAGENTA = "magenta"
    DIM = "dim"
    WHITE = "white"


ACTION_STATUS_STYLE = {
    ActionStatus.CREATE: UIStyle.GREEN.value,
    ActionStatus.UPDATE: UIStyle.CYAN.value,
    ActionStatus.FIX: UIStyle.YELLOW.value,
    ActionStatus.REMOVE: UIStyle.MAGENTA.value,
    ActionStatus.NOOP: UIStyle.DIM.value,
    ActionStatus.CONFLICT: UIStyle.RED.value,
}
