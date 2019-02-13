from ..meta_data import FieldMetaData


class DecodingError(Exception):
    pass


class EncodingError(Exception):
    pass


class FieldValueError(DecodingError):

    def __init__(self, field: FieldMetaData, expected: bytes, received: bytes) -> None:
        super().__init__(f'field {field.number} ("{field.name}" expected "{expected}" received "{received}"')
        self.field = field
        self.expected = expected
        self.received = received


class InvalidFieldError(DecodingError):

    def __init__(self, field: bytes, value: bytes) -> None:
        super().__init__(f'received unknown field "{field}" with value "{value}"')


class InvalidMsgTypeError(DecodingError):

    def __init__(self, msgtype: bytes) -> None:
        super().__init__(f'received unknown msgtype "{msgtype}"')
