"""Messages"""

from typing import Mapping, Any, Optional
from collections import OrderedDict
from ..meta_data import FieldMetaData, ComponentMetaData, MessageMemberMetaData, MessageMetaData


def _to_message_member_meta_data(
        info: Mapping[str, Any],
        field_meta_data: Mapping[str, FieldMetaData],
        component_meta_data: Optional[Mapping[str, ComponentMetaData]]
) -> Mapping[str, MessageMemberMetaData]:
    member = OrderedDict()

    for name, value in info.items():
        if value['type'] == 'field':
            field = field_meta_data[name]
            member[name] = MessageMemberMetaData(
                field, value['type'], value['required'])
        elif value['type'] == 'group':
            field = field_meta_data[name]
            member[name] = MessageMemberMetaData(
                field,
                value['type'],
                value['required'],
                _to_message_member_meta_data(
                    value['fields'], field_meta_data, component_meta_data)
            )
        elif value['type'] == 'component':
            component = component_meta_data[name]
            member[name] = MessageMemberMetaData(
                component, value['type'], value['required'])
        else:
            raise RuntimeError(f'unknown type "{value["type"]}"')
    return member


def _to_message_meta_data(
        name: str,
        info: Mapping[str, Any],
        field_meta_data: Mapping[str, FieldMetaData],
        component_meta_data: Mapping[str, ComponentMetaData]
) -> MessageMetaData:
    return MessageMetaData(
        name,
        info['msgtype'].encode('ascii'),
        info['msgcat'],
        _to_message_member_meta_data(
            info['fields'] or {}, field_meta_data, component_meta_data)
    )


def parse_messages(
        messages: Mapping[str, Any],
        field_meta_data: Mapping[str, FieldMetaData],
        component_meta_data: Mapping[str, ComponentMetaData]
) -> Mapping[str, MessageMetaData]:
    return {
        name: _to_message_meta_data(
            name, info, field_meta_data, component_meta_data)
        for name, info in messages.items()
    }
