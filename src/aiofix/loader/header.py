from typing import Mapping, Any
from ..meta_data import FieldMetaData, ComponentMetaData, MessageMemberMetaData
from .messages import _to_message_member_meta_data


def parse_header(
        info: Mapping[str, Any],
        field_meta_data: Mapping[str, FieldMetaData],
        component_meta_data: Mapping[str, ComponentMetaData]
) -> Mapping[str, MessageMemberMetaData]:
    return _to_message_member_meta_data(info, field_meta_data, component_meta_data)
