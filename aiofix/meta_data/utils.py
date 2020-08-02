"""Utils"""

from typing import ValuesView, Iterator, cast

from .message_member import MessageMemberMetaData, ComponentMetaData


def message_member_iter(
        message_members: ValuesView[MessageMemberMetaData]
) -> Iterator[MessageMemberMetaData]:
    for message_member in message_members:
        if message_member.type == 'component':
            component = cast(ComponentMetaData, message_member.member)
            yield from message_member_iter(component.members.values())
        else:
            yield message_member
