import copy
import re
from abc import ABCMeta, abstractmethod
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any

from dateutil.parser import parse

from . import constants
from .validate import ValidationError, Email


class Field(metaclass=ABCMeta):
    """Base class for all field types"""

    EMPTY_VALUES = (None, "", [], (), {})
    default_validators = []  # Default set of migration_tools
    default_preprocessors = []  # Default set of preprocessors
    default_postprocessors = []  # Default set of preprocessors
    default_error_messages = {
        "required": constants.REQUIRED.message,
        "incorrect_value": constants.INCORRECT_VALUE.message,
        "nonexistent_value_from_picklist": (
            constants.NONEXISTENT_VALUE_FROM_PICKLIST.message
        ),
    }

    def __init__(
        self,
        verbose_name: str = None,
        required: bool = True,
        default: Any = None,
        validators: tuple = (),
        preprocessors: tuple = (),
        postprocessors: tuple = (),
        error_messages: dict = None,
        **kwargs,
    ):
        self.instance = None
        self.verbose_name = verbose_name
        self.required = required
        self.default = default
        self.validators = [*self.default_validators, *validators]
        self.preprocessors = [*self.default_validators, *preprocessors]
        self.postprocessors = [*self.default_validators, *postprocessors]
        self.kwargs = kwargs

        # Collect default error message from self and parent classes
        messages = {}
        for cls in reversed(self.__class__.__mro__):
            messages.update(getattr(cls, "default_error_messages", {}))
        messages.update(error_messages or {})
        self.error_messages = messages

    def __str__(self):
        return "<%s:%s>" % (self.__class__.__name__, self.attr_name)

    def error(self, key, **kwargs):
        """A helper method that format the messages."""
        kwargs["row_number"] = self.instance.row_number
        kwargs["field"] = self.verbose_name

        try:
            if isinstance(key, constants.Tip):
                msg = key.message
            else:
                msg = self.error_messages[key]
        except KeyError:
            class_name = self.__class__.__name__
            msg = constants.MISSING_ERROR_MESSAGE.format(class_name=class_name, key=key)

        if isinstance(msg, str):
            msg = msg.format(**kwargs)

        self.instance.errors.append(msg)

    def _run_validators(self, value):
        if value in self.EMPTY_VALUES:
            return None

        for v in self.validators:
            try:
                v(value)
            except ValidationError:
                self.error(constants.INCORRECT_VALUE, value=self.original_value)

    def _run_processors(self, value, processors):
        if value in self.EMPTY_VALUES:
            return None

        original_value = copy.deepcopy(value)
        for v in processors:
            try:
                value = v(value)
            except ValidationError:
                self.error(constants.INCORRECT_VALUE, value=original_value)
                value = None
                break

        return value

    def _run_preprocessors(self, value):
        return self._run_processors(value, self.preprocessors)

    def _run_postprocessors(self, value):
        return self._run_processors(value, self.postprocessors)

    def _validate_missing(self, value):
        """检查required"""

        if value is None and self.required:
            self.error(constants.REQUIRED, value=value)

    def _validated(self, value):
        pass

    def check(self, value):
        # 检查自定义validators

        self._run_validators(value)

        return value

    def deserialize(self, value):
        """Deserialize ``value``."""
        # 格式化 value
        # check value -> 出现错误时，返回 None or default value

        self._validate_missing(value)
        self._validated(value)

        output = self._run_preprocessors(value)
        if value not in self.EMPTY_VALUES:
            output = self._deserialize(output)

        output = self._run_postprocessors(output)
        self.check(output)
        return output

    @abstractmethod
    def _deserialize(self, value):
        """目的: 把value格式化成对应的类型, 是为了被继承后，必须实现的method"""

        return value

    @staticmethod
    def pre_process_data(value):
        """转化 value"""
        return None if str(value).lower() in ("null", "n/a") else value

    def __set_name__(self, owner, name):
        self.attr_name = name
        self.private_name = f"_{name}"
        self.private_original_name = f"_{name}_original"

    def __get__(self, instance, owner):
        value = getattr(instance, self.private_name)
        value = self.default if value is None else value
        return value

    def __set__(self, instance, value):
        self.instance = instance
        self.original_value = value
        new_value = self.pre_process_data(value)
        new_value = self.deserialize(new_value)
        setattr(instance, self.private_name, new_value)
        if not hasattr(instance, self.private_original_name):
            setattr(instance, self.private_original_name, self.original_value)

    def __deepcopy__(self, memo):
        ret = copy.copy(self)
        return ret


class StrField(Field):
    """A string field."""

    def __init__(self, *args, min_len=None, max_len=None, strip=True, **kwargs):
        super(StrField, self).__init__(*args, **kwargs)
        self.min_len = min_len
        self.max_len = max_len
        self.strip = strip

    def _deserialize(self, value):
        try:
            value = str(value).strip() if self.strip else str(value)

            if value is not None and (
                (self.min_len is not None and len(value) < self.min_len)
                or (self.max_len is not None and len(value) > self.max_len)
            ):
                raise ValueError("Invalid Value.")

        except ValueError:
            self.error(constants.INCORRECT_VALUE, value=self.original_value)
            value = None

        return value


class EmailField(Field):
    """A Decimal field."""

    def _deserialize(self, value):
        try:
            Email()(str(value).strip())
        except ValidationError:
            self.error(constants.INCORRECT_VALUE, value=self.original_value)
            value = None

        return value


class DateField(Field):
    """A Date field."""

    def _deserialize(self, value):
        if isinstance(value, datetime):
            value = value.date()
        elif isinstance(value, date):
            pass
        elif isinstance(value, str):
            try:
                value = parse(
                    value,
                    default=datetime.now().replace(
                        day=1, hour=0, minute=0, second=0, microsecond=0
                    ),
                ).date()
            except ValueError:
                self.error(constants.INCORRECT_VALUE, value=self.original_value)
                value = None
        else:
            self.error(constants.INCORRECT_VALUE, value=self.original_value)
            value = None

        return value


class DatetimeField(Field):
    """A DateTime field."""

    def _deserialize(self, value):
        if isinstance(value, datetime):
            pass
        elif isinstance(value, str):
            try:
                value = parse(value)
            except ValueError:
                self.error(constants.INCORRECT_VALUE, value=self.original_value)
                value = None
        else:
            self.error(constants.INCORRECT_VALUE, value=self.original_value)
            value = None

        return value


class BooleanField(Field):
    # Values that will (de)serialize to `True`. If an empty set, any non-falsy
    #  value will deserialize to `True`.
    truthy = {"t", "T", "true", "True", "TRUE", "1", 1, True, "yes", "Yes", "YES"}
    # Values that will (de)serialize to `False`.
    falsy = {"f", "F", "false", "False", "FALSE", "0", 0, 0.0, False, "no", "No", "NO"}

    def _deserialize(self, value):
        if not self.truthy:
            return bool(value)
        else:
            try:
                if value in self.truthy:
                    return True
                elif value in self.falsy:
                    return False
                else:
                    self.error(constants.INCORRECT_VALUE, value=self.original_value)
                    return None
            except TypeError:
                self.error(constants.INCORRECT_VALUE, value=self.original_value)
                return None


class EnumField(Field):
    """Enumeration field.

    :param enumeration:
        Enumeration class (a subclass of ``enum.Enum``, Python>=3.4. only)

    :param kwargs:
        The same keyword arguments that :class:`Field` receives.

    """

    def __init__(self, enumeration, *args, **kwargs):
        self.enumeration = enumeration
        super(EnumField, self).__init__(*args, **kwargs)

    def _deserialize(self, value):
        enumeration = {
            element.value.lower(): element.value for element in self.enumeration
        }
        try:
            return self.enumeration(enumeration.get(value.lower()))
        except (ValueError, AttributeError):
            self.error(
                constants.NONEXISTENT_VALUE_FROM_PICKLIST, value=self.original_value
            )
            return None


class IntField(Field):
    """An integer field."""

    def __init__(self, *args, min_value=None, max_value=None, **kwargs):
        super(IntField, self).__init__(*args, **kwargs)
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value):
        if value is not None and self.min_value is not None and self.min_value > value:
            self.error(constants.INCORRECT_VALUE, value=self.original_value)
            value = None

        if value is not None and self.max_value is not None and self.min_value < value:
            self.error(constants.INCORRECT_VALUE, value=self.original_value)
            value = None

        return value

    def _deserialize(self, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            self.error(constants.INCORRECT_VALUE, value=self.original_value)
            value = None

        return value


class FloatField(Field):
    """An Float field."""

    def _deserialize(self, value):
        try:
            value = float(value)
        except ValueError:
            self.error(constants.INCORRECT_VALUE, value=self.original_value)
            value = None

        return value


class DecimalField(Field):
    """A Decimal field."""

    def __init__(
        self,
        *args,
        places=None,
        places_limit=None,
        rounding=None,
        min_value=None,
        max_value=None,
        **kwargs,
    ):
        super(DecimalField, self).__init__(*args, **kwargs)
        self.places = places
        self.places_limit = places_limit
        self.rounding = rounding
        self.min_value = min_value
        self.max_value = max_value

    def _validate_place(self, value):
        if self.places_limit and abs(value.as_tuple().exponent) > self.places_limit:
            self.error(constants.INCORRECT_VALUE, value=value.to_eng_string())
            value = None

        return value

    def _deserialize(self, value):
        try:
            value = Decimal(str(value))
            self._validate_place(value)
            if self.places is not None and value.is_finite():
                value = value.quantize(self.places, rounding=self.rounding)

            if value is not None and (
                (self.min_value is not None and value < self.min_value)
                or (self.max_value is not None and value > self.max_value)
            ):
                value = None
                self.error(constants.INCORRECT_VALUE, value=self.original_value)

        except (ValueError, InvalidOperation):
            self.error(constants.INCORRECT_VALUE, value=self.original_value)
            value = None
        return value


class Processor(metaclass=ABCMeta):
    """Base abstract class for Processor."""

    EMPTY_VALUES = (None, "", [], (), {})

    def __call__(self, value, *args, **kwargs):
        if value not in self.EMPTY_VALUES:
            value = self._run(value, *args, **kwargs)

        return value

    @abstractmethod
    def _run(self, value, *args, **kwargs):
        pass


class Validator(Processor, metaclass=ABCMeta):
    """Base abstract class for validators."""


class StrWithNumberValidator(Validator):
    """
    验证字符串中不能含有数字
    """

    @staticmethod
    def has_number(value):
        re_numbers = re.compile(r"\d")
        return False if (re_numbers.search(value) is None) else True

    def _run(self, value, *args, **kwargs):
        if value is not None and self.has_number(str(value)):
            raise ValidationError("Invalid Value.")


class PhoneAreaCodeValidator(Validator):
    area_code_list = constants.AREA_CODE
    re_compile = re.compile(r"^\+\d+$")

    def _run(self, value, *args, **kwargs):
        if not self.re_compile.match(value) or str(value) not in self.area_code_list:
            raise ValidationError("Invalid Value.")


class PhoneNumberValidator(Validator):
    def _run(self, value, *args, **kwargs):
        if not value.isdigit():
            raise ValidationError("Invalid Value.")


class EnumLimitationValidator(Validator):
    """
    Example::
        contact_type = fields.EnumField(
            enumeration=m.ContactType,
            verbose_name="Relationship with the Student",
            required=True,
            validators=(ContactTypeLimitationValidator((m.ContactType.EMERGENCY,)),),
        )

    """

    def __init__(self, enum_types: tuple, *args, **kwargs):
        super(EnumLimitationValidator, self).__init__(*args, **kwargs)
        self.enum_types = enum_types

    def _run(self, value, *args, **kwargs):
        if value is not None and value not in self.enum_types:
            raise ValidationError("Invalid Value.")


class Preprocessor(Processor, metaclass=ABCMeta):
    """Base abstract class for Preprocessor."""


class ReplacePreprocessor(Preprocessor):
    def __init__(self, old, new, *args, **kwargs):
        super(ReplacePreprocessor, self).__init__(*args, **kwargs)
        self.old = old
        self.new = new

    def _run(self, value, *args, **kwargs):
        try:
            value = str(value).replace(self.old, self.new)
        except AttributeError:
            raise ValidationError("Invalid Value.")

        return value


class LowerPreprocessor(Preprocessor):
    def _run(self, value, *args, **kwargs):
        try:
            value = str(value).lower()
        except AttributeError:
            raise ValidationError("Invalid Value.")

        return value


class CapitalizePreprocessor(Preprocessor):
    def _run(self, value, *args, **kwargs):
        try:
            value = str(value).capitalize()
        except AttributeError:
            raise ValidationError("Invalid Value.")

        return value
