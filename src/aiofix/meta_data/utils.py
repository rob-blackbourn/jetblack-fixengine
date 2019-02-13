from typing import ValuesView, Iterator
from .message_member import MessageMemberMetaData


def message_member_iter(members: ValuesView[MessageMemberMetaData]) -> Iterator[MessageMemberMetaData]:
    for member in members:
        if member.type == 'component':
            yield from message_member_iter(member.member.members.values())
        else:
            yield member
