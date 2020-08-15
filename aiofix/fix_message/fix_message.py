"""Parsing FX messages"""

from __future__ import annotations

from copy import deepcopy
from typing import Optional

from ..meta_data import (
    ProtocolMetaData,
    MessageMetaData,
    FieldMessageDataMap
)

from .encoder import encode, SOH
from .decoder import decode, find_message_meta_data


class FixMessage:

    def __init__(
            self,
            protocol: ProtocolMetaData,
            data: FieldMessageDataMap,
            meta_data: Optional[MessageMetaData] = None
    ) -> None:
        self.protocol = protocol
        self.data = deepcopy(data)
        self.meta_data = meta_data or find_message_meta_data(protocol, data)

    @classmethod
    def decode(
            cls,
            protocol: ProtocolMetaData,
            buf: bytes,
            *,
            strict: bool = True,
            validate: bool = True,
            sep: bytes = SOH,
            convert_sep_for_checksum: bool = True
    ) -> FixMessage:
        data, meta_data = decode(
            protocol,
            buf,
            strict=strict,
            validate=validate,
            sep=sep,
            convert_sep_for_checksum=convert_sep_for_checksum
        )
        return FixMessage(protocol, data, meta_data)

    def encode(
            self,
            sep: bytes = SOH,
            regenerate_integrity: bool = True,
            convert_sep_for_checksum: bool = False
    ) -> bytes:
        return encode(
            self.protocol,
            self.data,
            self.meta_data,
            sep=sep,
            regenerate_integrity=regenerate_integrity,
            convert_sep_for_checksum=convert_sep_for_checksum
        )
