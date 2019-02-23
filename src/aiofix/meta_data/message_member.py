from __future__ import annotations
from typing import Mapping, Optional, Union, MutableMapping, List, Any


class FieldMetaData:

    def __init__(self, name: str, number: bytes, type_: str, values: Optional[Mapping[bytes, str]] = None) -> None:
        self._name = name
        self._number = number
        self._type = type_
        self._values = values
        self._values_by_name = {value: name for name, value in values.items()} if values else None

    @property
    def name(self) -> str:
        return self._name

    @property
    def number(self) -> bytes:
        return self._number

    @property
    def type(self) -> str:
        return self._type

    @property
    def values(self) -> Optional[Mapping[bytes, str]]:
        return self._values

    @property
    def values_by_name(self) -> Optional[Mapping[str, bytes]]:
        return self._values_by_name

    def __str__(self) -> str:
        return f'<FieldMetaData: name="{self.name}", number="{self.number}", type="{self.type}", values={self.values}'

    __repr__ = __str__


class ComponentMetaData:

    def __init__(self, name: str, members: Optional[Mapping[str, MessageMemberMetaData]]) -> None:
        self._name = name
        self._members = members

    @property
    def name(self) -> str:
        return self._name

    @property
    def members(self) -> Optional[Mapping[str, MessageMemberMetaData]]:
        return self._members

    def __str__(self) -> str:
        return f'<ComponentMetaData: name="{self.name}", members={self.members}'

    __repr__ = __str__


class MessageMemberMetaData:

    def __init__(
            self,
            member: Union[FieldMetaData, ComponentMetaData],
            type_: str,
            is_required: bool,
            children: Optional[Mapping[str, MessageMemberMetaData]] = None
    ) -> None:
        self._member = member
        self._type = type_
        self._is_required = is_required
        self._children = children

    @property
    def member(self) -> Union[FieldMetaData, ComponentMetaData]:
        return self._member

    @property
    def type(self) -> str:
        return self._type

    @property
    def is_required(self) -> bool:
        return self._is_required

    @property
    def children(self) -> Optional[Mapping[str, MessageMemberMetaData]]:
        return self._children

    def __str__(self) -> str:
        return f'<MessageMemberMetaData: member={self.member}, is_required={self.is_required}, children={self.children}>'

    __repr__ = __str__


MessageFieldMetaDataMapping = Mapping[str, Union[MessageMemberMetaData, 'MessageFieldMetaDataMapping']]

FieldMessageDataMap = MutableMapping[str, Union[Any, List['FieldMessageDataMap']]]
