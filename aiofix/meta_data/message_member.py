""""Message members"""

from __future__ import annotations
from typing import Mapping, Optional, Union, MutableMapping, List, Any


class FieldMetaData:
    """Field meta data"""

    def __init__(
            self,
            name: str,
            number: bytes,
            type_: str,
            values: Optional[Mapping[bytes, str]] = None
    ) -> None:
        self.name = name
        self.number = number
        self.type = type_
        self.values = values
        self.values_by_name = {
            value: name for name,
            value in values.items()
        } if values else None

    def __str__(self) -> str:
        return f'<FieldMetaData: name="{self.name}", number="{self.number!r}", type="{self.type}", values={self.values}'

    __repr__ = __str__


class ComponentMetaData:
    """Component meta data"""

    def __init__(
            self,
            name: str,
            members: Mapping[str, MessageMemberMetaData]
    ) -> None:
        self.name = name
        self.members = members

    def __str__(self) -> str:
        return f'<ComponentMetaData: name="{self.name}", members={self.members}'

    __repr__ = __str__


class MessageMemberMetaData:
    """The meta data for a message member"""

    def __init__(
            self,
            member: Union[FieldMetaData, ComponentMetaData],
            type_: str,
            is_required: bool,
            children: Optional[Mapping[str, MessageMemberMetaData]] = None
    ) -> None:
        self.member = member
        self.type = type_
        self.is_required = is_required
        self.children = children

    def __str__(self) -> str:
        return f'<MessageMemberMetaData: member={self.member}, is_required={self.is_required}, children={self.children}>'

    __repr__ = __str__


MessageFieldMetaDataMapping = Mapping[
    str,
    Union[MessageMemberMetaData, 'MessageFieldMetaDataMapping']
]

FieldMessageDataMap = MutableMapping[
    str,
    Union[Any, List['FieldMessageDataMap']]
]
