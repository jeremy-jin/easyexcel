from collections import namedtuple
from enum import Enum

Tip = namedtuple("Tip", ["message", "description"])


class MessageLevel(Enum):
    ERROR = "error"
    WARNING = "warning"


MISSING_ERROR_MESSAGE = (
    "ValidationError raised by `{class_name}`, but error key `{key}` does "
    "not exist in the `error_messages` dictionary."
)


# Global/Format
TEMPLATE_ERROR = Tip(
    message="Template error",
    description="If the template is not in the correct format",
)
REQUIRED = Tip(
    message="Missing value: Column `{field}`",
    description="If the field is mandatory but marked as Null or empty",
)

# 表示输入的值和要求不一致(包含配置不再系统中)
INCORRECT_VALUE = Tip(
    message="Incorrect value - {field} = `{value}`",
    description=(
        """
        If the field value does not match the field format
        or is not in the code level options list (e.g. Gender)
        """
    ),
)

# 表示输入的值不再枚举范围内
NONEXISTENT_VALUE_FROM_PICKLIST = Tip(
    message="Nonexistent value from the picklist - {field} = `{value}`",
    description=(
        """
        If the field value does not match the field format
        or is not in the code level options list (e.g. Gender)
        """
    ),
)
