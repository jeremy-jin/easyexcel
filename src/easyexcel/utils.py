import re
from collections import OrderedDict, UserDict, namedtuple
from datetime import date, datetime
from enum import Enum

LAZY_PROPERTIES_FIELD_NAME = "__lazy_properties__"


class CollectionProxy(object):
    def __init__(self, items):
        self._items = items

    def __getattr__(self, name):
        def spawning_method(*args, **kwargs):
            items = self._items

            def call(item):
                return getattr(item, name)(*args, **kwargs)

            if items:
                return list(map(call, self._items))

        return spawning_method


def serialize_dict(data):
    def _serialize(value):
        if isinstance(value, (list, dict, bool, int, float, str, type(None))):
            return value
        elif isinstance(value, (date, datetime)):
            return value.isoformat()
        elif isinstance(value, Enum):
            return value.value
        return str(value)

    return OrderedDict((k, _serialize(v)) for k, v in data.items())


class CusEnum(Enum):
    @property
    def message(self):
        return self.value.message


def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


class LazyProperty:
    """
    Classes with lazy loading properties

    The following example uses decorators to modify properties
    to achieve lazy loading of properties::

        class Foo(object):
            def __init__(self):
                self.data = 1

            @LazyProperty
            def boo(self):
                return self.data + 1

    ** Parameter ``mark``, Mark whether the lazy loading property name
    is placed inside the list in the object as a record.

    If `mark` is `True`, Follow the example above::

        >>> class Foo(object):
        ...    def __init__(self):
        ...        self.data = 1
        ...
        ...    @LazyProperty(mark=True)
        ...    def boo(self):
        ...        return self.data + 1

        >>> foo = Foo()
        >>> print(dir(foo))
        # ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__',
        # '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__',
        # '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__',
        # '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__',
        # '__str__', '__subclasshook__', '__weakref__', 'boo', 'data']

        >>> foo.boo
        >>> print(dir(foo))
        # ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__',
        # '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__',
        # '__init_subclass__', '__lazy_properties__', '__le__', '__lt__', '__module__',
        # '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__',
        # '__sizeof__', '__str__', '__subclasshook__', '__weakref__', 'boo', 'data']

        >>> print(foo.__lazy_properties__)
        # ["foo"]

    """

    LAZY_PROPERTIES_FIELD_NAME = LAZY_PROPERTIES_FIELD_NAME or "__lazy_properties__"

    def __init__(self, func=None, mark=False):
        self.func = func
        self.mark = mark

    def __call__(self, func, *args, **kwargs):
        self.func = func
        return self

    def __get__(self, instance, owner):
        value = self.func(instance)
        setattr(instance, self.func.__name__, value)
        if self.mark:
            self.__add_lazy_property(instance, self.func.__name__)
        return value

    def __add_lazy_property(self, instance, name):
        """Send the lazy loading property name in the object for record"""

        lazy_properties = getattr(instance, self.LAZY_PROPERTIES_FIELD_NAME, None)
        if lazy_properties:
            lazy_properties.append(name)
        else:
            lazy_properties = [name]
            setattr(instance, self.LAZY_PROPERTIES_FIELD_NAME, lazy_properties)


class UnLazyProperty:
    """Use with class ``LazyProperty`` to
    unload properties that have been lazy loaded.

    The following example demonstrates a lazy loading property being reloaded::

        >>> class Foo(object):
        ...    changed = UnLazyProperty(False)
        ...
        ...    def __init__(self):
        ...        self.data = 1
        ...
        ...    @LazyProperty(mark=True)
        ...    def boo(self):
        ...        return self.data + 1

        >>> foo = Foo()
        >>> foo.boo # print 2
        >>> print(dir(foo))
        # ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__',
        # '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__',
        # '__init_subclass__', '__lazy_properties__', '__le__', '__lt__', '__module__',
        # '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__',
        # '__sizeof__', '__str__', '__subclasshook__', '__weakref__', 'boo', 'changed',
        # 'data']
        >>> print(foo.__lazy_properties__)
        # ["foo"]
        >>> foo.data = 2
        >>> foo.changed = True
        >>> print(dir(foo))
        # ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__',
        # '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__',
        # '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__',
        # '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__',
        # '__str__', '__subclasshook__', '__weakref__', 'boo', 'changed', 'data']
        >>> foo.boo # print 3
        >>> print(dir(foo))
        # ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__',
        # '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__',
        # '__init_subclass__', '__lazy_properties__', '__le__', '__lt__', '__module__',
        # '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__',
        # '__sizeof__', '__str__', '__subclasshook__', '__weakref__', 'boo', 'changed',
        # 'data']


    """

    LAZY_PROPERTIES_FIELD_NAME = LAZY_PROPERTIES_FIELD_NAME or "__lazy_properties__"

    def __init__(self, value):
        self.value = value

    def __set__(self, instance, value):
        if value is True:
            lazy_properties = (
                getattr(instance, self.LAZY_PROPERTIES_FIELD_NAME, []) or []
            )
            if hasattr(instance, self.LAZY_PROPERTIES_FIELD_NAME):
                delattr(instance, self.LAZY_PROPERTIES_FIELD_NAME)
            for lazy_property in lazy_properties:
                delattr(instance, lazy_property)
        self.value = value


class DefaultListDict(UserDict):
    """Customize the dictionary with default value [],
    the value type of the dictionary is list.
    """

    def __missing__(self, key):
        """Default [] is returned in case of missing key"""

        self[key] = value = self.__default_value__()
        return value

    def __setitem__(self, key, value):
        self.__validate__(value)
        self.data[key] = value

    def __getattr__(self, item):
        return self[item]

    @staticmethod
    def __validate__(value):
        if not isinstance(value, list):
            raise TypeError(f"Must be of type `list`, but now it is `{type(value)}`.")

    @staticmethod
    def __default_value__():
        return list()

    def add(self, key, value):
        self[key].append(value)

    def insert(self, key, value, index: int):
        self[key].insert(index, value)


class ExecCommandError(Exception):
    pass


Command = namedtuple("Command", "func, args, kwargs")


def identify(obj):
    """Get the object id of string type"""
    return str(id(obj))


class RollbackCommands(DefaultListDict):
    """Collect rollback commands"""

    def add(self, container, command):
        identify_id = identify(container)
        self.validate(command)
        super().add(identify_id, command)

    @staticmethod
    def _generate_command(func, args=None, kwargs=None):
        args = args if args else ()
        kwargs = kwargs if kwargs else {}
        command = Command(func=func, args=args, kwargs=kwargs)
        return command

    def append_command(self, container, func, args=None, kwargs=None):
        self.add(container, self._generate_command(func, args=args, kwargs=kwargs))

    def insert(self, container, command, index: int):
        identify_id = identify(container)
        self.validate(command)
        super().insert(identify_id, command, index)

    def insert_command(self, container, index, func, args=None, kwargs=None):
        self.insert(
            container,
            self._generate_command(func, args=args, kwargs=kwargs),
            index=index,
        )

    @staticmethod
    def validate(command):
        if not isinstance(command, Command):
            raise TypeError(
                f"Must be an instance of `:Command:`, "
                f"but now it's `{command.__class__}`."
            )

    def exec_commands(self, identify_id):
        # identify_id = identify(container)
        commands = self.pop(identify_id, [])
        for command in commands:
            try:
                command.func(*command.args, **command.kwargs)
            except Exception:
                raise ExecCommandError(
                    f"func: {command.func.__name__}, args: {command.args}, kwargs: {command.kwargs}"
                )


class DispatchCommands(RollbackCommands):
    """Collect events that need to be dispatched"""

    pass
