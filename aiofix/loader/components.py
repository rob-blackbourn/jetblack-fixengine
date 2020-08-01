"""Components"""

from typing import Mapping, Any, Optional
from ..meta_data import FieldMetaData, ComponentMetaData
from .messages import _to_message_member_meta_data


def parse_components(
        info: Optional[Mapping[str, Any]],
        field_meta_data: Mapping[str, FieldMetaData]
) -> Mapping[str, ComponentMetaData]:
    if info is None:
        return dict()

    # Declare components first to handle forward references.
    components = {name: ComponentMetaData(name, None) for name in info.keys()}
    for name, data in info.items():
        component: ComponentMetaData = components[name]
        component._members = _to_message_member_meta_data(
            data,
            field_meta_data,
            components
        )
    return components
