import re


class ValidationError(Exception):
    pass


class Validator(object):
    """Base abstract class for validators.

    .. note::
        This class does not provide any behavior. It is only used to
        add a useful `__repr__` implementation for validators.
    """

    def __repr__(self):
        args = self._repr_args()
        args = "{0}, ".format(args) if args else ""

        return "<{self.__class__.__name__}({args}error={self.error!r})>".format(
            self=self, args=args
        )

    def _repr_args(self):
        """A string representation of the args passed to this validator. Used by
        `__repr__`.
        """
        return ""


class Email(Validator):
    """Validate an email address.

    :param str error: Error message to raise in case of a validation error. Can be
        interpolated with `{input}`.
    """

    USER_REGEX = re.compile(
        r"(^[-!#$%&'*+/=?^`{}|~\w]+(\.[-!#$%&'*+/=?^`{}|~\w]+)*$"  # dot-atom
        # quoted-string
        r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]'
        r'|\\[\001-\011\013\014\016-\177])*"$)',
        re.IGNORECASE | re.UNICODE,
    )

    DOMAIN_REGEX = re.compile(
        # domain
        r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+" r"(?:[A-Z]{2,6}|[A-Z0-9-]{2,})$"
        # literal form, ipv4 address (SMTP 4.1.3)
        r"|^\[(25[0-5]|2[0-4]\d|[0-1]?\d?\d)"
        r"(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\]$",
        re.IGNORECASE | re.UNICODE,
    )

    DOMAIN_WHITELIST = ("localhost",)

    default_message = "Not a valid email address."

    def __init__(self, error=None):
        self.error = error or self.default_message

    def _format_error(self, value):
        return self.error.format(input=value)

    def __call__(self, value):
        message = self._format_error(value)

        if not value or "@" not in value:
            raise ValidationError(message)

        user_part, domain_part = value.rsplit("@", 1)

        if not self.USER_REGEX.match(user_part):
            raise ValidationError(message)

        if domain_part not in self.DOMAIN_WHITELIST:
            if not self.DOMAIN_REGEX.match(domain_part):
                try:
                    domain_part = domain_part.encode("idna").decode("ascii")
                except UnicodeError:
                    pass
                else:
                    if self.DOMAIN_REGEX.match(domain_part):
                        return value
                raise ValidationError(message)

        return value
