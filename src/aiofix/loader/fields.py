from typing import Mapping, Any
from ..meta_data import FieldMetaData


def _to_field_meta_data(name: str, info: Mapping[str, Any]) -> FieldMetaData:
    values = {
        value.encode('ascii'): description
        for value, description in info['values'].items()
    } if 'values' in info and info['values'] else None
    return FieldMetaData(name, info['number'].encode('ascii'), info['type'], values)


def parse_fields(fields: Mapping[str, Any]) -> Mapping[str, FieldMetaData]:
    return {name: _to_field_meta_data(name, info) for name, info in fields.items()}
