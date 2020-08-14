"""Test the loader"""

from ruamel.yaml import YAML  # type: ignore

from aiofix.loader.loader import load_protocol, convert_xml_file_to_dict


def test_loader():
    protocol = load_protocol('etc/FIX44.xml')
    assert protocol is not None


def test_xml():
    for name in ['FIX40', 'FIX41', 'FIX42', 'FIX43', 'FIX44']:
        dct = convert_xml_file_to_dict('etc/' + name + '.xml')
        assert dct is not None
        with open('etc/' + name + '.yaml', 'wt') as file_ptr:
            yaml = YAML()  # type: ignore
            yaml.dump(dct, file_ptr)  # type: ignore
