import copy
import inspect
from abc import ABCMeta
from collections import defaultdict

from .constants import MessageLevel
from .fields import Field
from . import constants
from .utils import LazyProperty, identify


def post_load(func):
    """标记类方法需要在loaded后执行"""

    func.__post_load__ = True
    return func


class ModelMetaclass(type):
    def __new__(mcs, name, bases, attrs, **kwargs):
        # 目的是收集字段信息 --> 准备在init时校验数据

        # Also ensure initialization is only performed for subclasses of Model
        # (excluding Model class itself).
        parents = [b for b in bases if isinstance(b, ModelMetaclass)]
        if not parents:
            return type.__new__(mcs, name, bases, attrs)

        # 获取继承的属性Field，目的是添加到新Class的收集字段declared_fields中
        # 方便之后在Class获取声明了哪些Field字段
        inherited_fields = dict()
        for parent in parents:
            _fields = getattr(parent, "declared_fields", {})
            inherited_fields.update(
                **{
                    field_name: copy.deepcopy(field)
                    for field_name, field in _fields.items()
                }
            )

        local_fields = dict()
        for attr_name, attr in attrs.items():
            if isinstance(attr, Field):
                local_fields[attr_name] = attr

        declared_fields = {**inherited_fields, **local_fields}
        attrs["declared_fields"] = declared_fields  # 保存属性和列的映射关系
        new_class = type.__new__(mcs, name, bases, attrs)
        return new_class

    def __init__(cls, name, bases, attrs):
        super(ModelMetaclass, cls).__init__(name, bases, attrs)
        cls._resolve_processors()

    def _resolve_processors(cls):
        mro = inspect.getmro(cls)
        cls._has_processors = False
        cls.__processors__ = set()
        for attr_name in dir(cls):
            # Need to look up the actual descriptor, not whatever might be
            # bound to the class. This needs to come from the __dict__ of the
            # declaring class.
            for parent in mro:
                try:
                    attr = parent.__dict__[attr_name]
                except KeyError:
                    continue
                else:
                    break
            else:
                # In case we didn't find the attribute and didn't break above.
                # We should never hit this - it's just here for completeness
                # to exclude the possibility of attr being undefined.
                continue

            try:
                attr.__post_load__
            except AttributeError:
                continue

            cls._has_processors = True
            cls.__processors__.add(attr_name)


class Model(metaclass=ModelMetaclass):
    def __init__(self, **kwargs):
        self.errors = []
        self.warnings = []
        # 先获取参数中的row_number，并设置为属性
        row_number = kwargs.get("row_number", None)
        self.row_number = row_number
        for k, v in kwargs.items():
            setattr(self, k, v)

        for name, field in self.declared_fields.items():
            if name not in kwargs:
                # 通过set方式，不需要单独调用validate
                setattr(self, name, None)

        self._invoke_processors()

    def _invoke_processors(self):
        for attr_name in self.__processors__:
            # This will be a bound method.
            getattr(self, attr_name)()

    def to_dict(self):
        data = dict()
        for name, _ in self.declared_fields.items():
            data[name] = getattr(self, name, None)
        return data

    def origin_data_to_dict(self, include_errors=False, include_warnings=False):
        data = dict()
        for name, _ in self.declared_fields.items():
            data[name] = getattr(self, f"_{name}_original", None)

        if include_errors:
            data["errors"] = self.errors

        if include_warnings:
            data["warnings"] = self.warnings

        return data

    def message(self, message_type, key, **kwargs):
        """A helper method that format the messages"""
        try:
            msg = key.message
        except KeyError:
            class_name = self.__class__.__name__
            msg = constants.MISSING_ERROR_MESSAGE.format(class_name=class_name, key=key)
        else:
            if isinstance(msg, str):
                msg = msg.format(**kwargs)

        getattr(self, message_type).append(msg)

    def error(self, key, **kwargs):
        self.message("errors", key, **kwargs)

    def warning(self, key, **kwargs):
        self.message("warnings", key, **kwargs)


class BaseObjectList(metaclass=ABCMeta):
    # 字段和Excel中的位置映射关系
    FIELDS = None

    # 生产对象的类(基本的验证放在对象中验证)
    Object = None

    # 默认的错误文案
    tip_messages = None

    # data字典中的对应data名称
    DATA_NAME = None

    # 错误级别
    _ERRORS = f"{MessageLevel.ERROR.value}s"
    _WARNINGS = f"{MessageLevel.WARNING.value}s"

    processor = None

    def __init__(
        self,
        origin_data,
        missing_value_level: MessageLevel = MessageLevel.ERROR,
        *args,
        **kwargs,
    ):
        self.origin_data = origin_data
        self.titles = None
        self.new_instances = dict()
        self.data = []
        self.config = dict()
        self.missing_value_level = missing_value_level
        self.can_next = True

    def error(self, instance, key, **kwargs):
        instance.error(key, **kwargs)

    def warning(self, instance, key, **kwargs):
        instance.warning(key, **kwargs)

    def load_titles(self):
        self.titles = self.origin_data.get(self.DATA_NAME, {}).get("titles", [])

    def load_data(self):
        for row_data in self.origin_data.get(self.DATA_NAME, {}).get("data", []):
            instance = self.Object(**row_data)
            self.data.append(instance)

    def load(self):
        self.load_titles()
        self.load_data()

    def load_config(self):
        self.make_config()

    def _mapping(self, attr: str):
        ret = defaultdict(list)
        [
            ret[getattr(instance, attr, None)].append(instance)
            for instance in self.data
            if getattr(instance, attr, None)
        ]

        return ret

    @staticmethod
    def make_mapping_key(instance, attrs: list[str] | tuple[str]):
        return "::".join(str(getattr(instance, attr, None)) for attr in attrs)

    @staticmethod
    def make_mapping_key_by_values(values: list | tuple):
        return "::".join([str(v) for v in values])

    def _mapping_multiple_fields(self, attrs: list[str] | tuple[str]):
        ret = defaultdict(list)
        [
            ret[self.make_mapping_key(instance, attrs)].append(instance)
            for instance in self.data
        ]

        return ret

    def post_validate(self):
        titles = list(self.FIELDS.values())
        if self.titles != titles:
            self.can_next = False
            if len(self.data) > 0:
                instance = self.data[0]
            else:
                empty_instance = self.Object()
                empty_instance.errors.clear()
                self.data.append(empty_instance)
                instance = empty_instance

            self.error(instance, constants.TEMPLATE_ERROR)

    @staticmethod
    def can_validate(instance):
        return True

    def validate(self):
        self.post_validate()
        if self.can_next:
            for instance in self.data:
                if self.can_validate(instance):
                    self._validate(instance)

            self._validate_relationship()

    def _validate_relationship(self):
        pass

    def _validate(self, instance):
        pass

    def save(self):
        if not self.data:
            return

        for instance in self.data:
            self._save(instance)

    def _save(self, instance):
        pass

    def make_config(self):
        pass

    @LazyProperty
    def top_landlord_id(self):
        return self.processor.top_landlord_id

    @LazyProperty
    def system_user_id(self):
        return self.processor.system_user_id

    @LazyProperty
    def property_id(self):
        return self.processor.property_id

    @LazyProperty
    def property_timezone(self):
        return self.processor.property_timezone

    @LazyProperty
    def property_currency(self):
        return self.processor.property_currency

    @LazyProperty
    def users_rpc(self):
        return self.processor.container.users_rpc

    @LazyProperty
    def locations_rpc(self):
        return self.processor.container.locations_rpc

    @LazyProperty
    def properties_rpc(self):
        return self.processor.container.properties_rpc

    @LazyProperty
    def configurations_rpc(self):
        return self.processor.container.configurations_rpc

    @LazyProperty
    def nominations_rpc(self):
        return self.processor.container.nominations_rpc

    @LazyProperty
    def prices_rpc(self):
        return self.processor.container.prices_rpc

    @LazyProperty
    def billing_rpc(self):
        return self.processor.container.billing_rpc

    @LazyProperty
    def process_controls_rpc(self):
        return self.processor.container.process_controls_rpc

    @LazyProperty
    def container(self):
        return self.processor.container

    @LazyProperty
    def storage(self):
        return self.processor.container.storage

    @staticmethod
    def get_field_verbose_name(instance, field_name):
        return instance.declared_fields[field_name].verbose_name

    def has_errors(self):
        is_errors = False
        for instance in self.data:
            if instance.errors:
                is_errors = True
                break

        return is_errors

    def get_result(self):
        res = []
        for instance in self.data:
            res.append(
                instance.origin_data_to_dict(include_errors=True, include_warnings=True)
            )

        return res

    def rollback(self):
        identify_id = identify(self.container)
        commands = self.rollback_commands.pop(identify_id, [])
        if not commands:
            return

        for command in commands:
            command.func(*command.args, **command.kwargs)
