"""Loader"""

from typing import Any, Dict
import xml.dom.minidom as minidom
import xml.dom as dom

from ruamel.yaml import YAML

from ..meta_data import ProtocolMetaData

from .fields import parse_fields
from .messages import parse_messages, parse_header, parse_components


def process_members(node: Any) -> Dict[str, Any]:
    members: Dict[str, Any] = {}
    for child in node.childNodes:
        if child.nodeType != dom.Node.ELEMENT_NODE:
            continue

        if child.nodeName == 'field':
            members[child.attributes['name'].value] = {
                'type': 'field',
                'required': child.attributes['required'].value == 'Y'
            }
        elif child.nodeName == 'group':
            members[child.attributes['name'].value] = {
                'type': 'group',
                'required': child.attributes['required'].value == 'Y',
                'fields': process_members(child)
            }
        elif child.nodeName == 'component':
            members[child.attributes['name'].value] = {
                'type': 'component',
                'required': child.attributes['required'].value == 'Y'
            }
        else:
            raise RuntimeError(f'invalid member node {child.nodeName}')
    return members


def process_message(node: Any) -> Dict[str, Any]:
    return {
        'msgtype': node.attributes['msgtype'].value,
        'msgcat': node.attributes['msgcat'].value,
        'fields': process_members(node)
    }


def process_field(node: Any) -> Dict[str, Any]:
    return {
        'number': node.attributes['number'].value,
        'type': node.attributes['type'].value,
        'values': {
            child.attributes['enum'].value: child.attributes['description'].value
            for child in node.childNodes if child.nodeType == dom.Node.ELEMENT_NODE
        }
    }


def process_messages(node: Any) -> Dict[str, Any]:
    return {
        child.attributes['name'].value: process_message(child)
        for child in node.childNodes if child.nodeType == dom.Node.ELEMENT_NODE and child.nodeName == 'message'
    }


def process_components(node: Any) -> Dict[str, Any]:
    return {
        child.attributes['name'].value: process_members(child)
        for child in node.childNodes if child.nodeType == dom.Node.ELEMENT_NODE and child.nodeName == 'component'
    }


def process_fields(node: Any) -> Dict[str, Any]:
    return {
        child.attributes['name'].value: process_field(child)
        for child in node.childNodes
        if child.nodeType == dom.Node.ELEMENT_NODE and child.nodeName == 'field'
    }


def process_root(node: Any) -> Dict[str, Any]:
    major = node.attributes['major'].value
    minor = node.attributes['minor'].value
    servicepack = node.attributes['servicepack'].value
    protocol = {
        'version': {
            'major': major,
            'minor': minor,
            'servicepack': servicepack
        },
        'beginString': 'FIX.' + major + '.' + minor,
        'fields': {},
        'components': {},
        'header': {},
        'trailer': {},
        'messages': {}
    }

    for child in node.childNodes:
        if child.nodeType != dom.Node.ELEMENT_NODE:
            continue

        if child.nodeName == 'header':
            protocol['header'] = process_members(child)
        elif child.nodeName == 'trailer':
            protocol['trailer'] = process_members(child)
        elif child.nodeName == 'messages':
            protocol['messages'] = process_messages(child)
        elif child.nodeName == 'components':
            protocol['components'] = process_components(child)
        elif child.nodeName == 'fields':
            protocol['fields'] = process_fields(child)
        else:
            raise RuntimeError(f'unknown node {child.nodeName}')

    return protocol


def convert_xml_file_to_dict(filename: str) -> Dict[str, Any]:
    document = minidom.parse(filename)
    config = process_root(document.documentElement)
    return config


def load_protocol(
        filename: str,
        *,
        is_millisecond_time: bool = True,
        is_float_decimal: bool = False,
        is_bool_enum: bool = False
) -> ProtocolMetaData:
    if filename.endswith('.xml'):
        config: Dict[str, Any] = convert_xml_file_to_dict(filename)
    elif filename.endswith('yaml') or filename.endswith('yml'):
        yaml = YAML()
        with open(filename, 'rt') as file_ptr:
            config = yaml.load(file_ptr)
    else:
        raise Exception('Unhandled file type')

    version = config['version']['major'] + '.' + config['version']['minor']
    begin_string = config['beginString'].encode('ascii')
    fields = parse_fields(config['fields'])
    components = parse_components(config['components'], fields)
    messages = parse_messages(config['messages'], fields, components)
    header = parse_header(config['header'], fields, components)
    trailer = parse_header(config['trailer'], fields, components)

    return ProtocolMetaData(
        version,
        begin_string,
        fields,
        components,
        messages,
        header,
        trailer,
        is_millisecond_time=is_millisecond_time,
        is_float_decimal=is_float_decimal,
        is_bool_enum=is_bool_enum
    )
