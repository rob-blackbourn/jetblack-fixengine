"""Loader"""

from collections import OrderedDict
import xml.dom.minidom as minidom
import xml.dom as dom
from ..meta_data import ProtocolMetaData
from .fields import parse_fields
from .messages import parse_messages
from .header import parse_header
from .components import parse_components


def process_members(node) -> dict:
    members = OrderedDict()
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


def process_message(node) -> dict:
    return {
        'msgtype': node.attributes['msgtype'].value,
        'msgcat': node.attributes['msgcat'].value,
        'fields': process_members(node)
    }


def process_field(node) -> dict:
    return {
        'number': node.attributes['number'].value,
        'type': node.attributes['type'].value,
        'values': {
            child.attributes['enum'].value: child.attributes['description'].value
            for child in node.childNodes if child.nodeType == dom.Node.ELEMENT_NODE
        }
    }


def process_messages(node) -> dict:
    return {
        child.attributes['name'].value: process_message(child)
        for child in node.childNodes if child.nodeType == dom.Node.ELEMENT_NODE and child.nodeName == 'message'
    }


def process_components(node) -> dict:
    return {
        child.attributes['name'].value: process_members(child)
        for child in node.childNodes if child.nodeType == dom.Node.ELEMENT_NODE and child.nodeName == 'component'
    }


def process_fields(node) -> dict:
    return {
        child.attributes['name'].value: process_field(child)
        for child in node.childNodes if child.nodeType == dom.Node.ELEMENT_NODE and child.nodeName == 'field'
    }


def process_root(node) -> dict:
    protocol = {
        'version': node.attributes['major'].value + '.' + node.attributes['minor'].value,
        'beginString': 'FIX.' + node.attributes['major'].value + '.' + node.attributes['minor'].value,
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


def load_protocol(
        filename,
        *,
        is_millisecond_time: bool = True,
        is_float_decimal: bool = False
) -> ProtocolMetaData:
    document = minidom.parse(filename)
    config = process_root(document.documentElement)

    version = config['version']
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
        is_float_decimal=is_float_decimal
    )
