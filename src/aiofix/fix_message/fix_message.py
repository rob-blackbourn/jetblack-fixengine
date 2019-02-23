from __future__ import annotations
from ..meta_data import (
    ProtocolMetaData,
    MessageMetaData,
    FieldMessageDataMap
)
from .encoder import encode, SOH
from .decoder import decode


class FixMessage:

    def __init__(
            self,
            protocol: ProtocolMetaData,
            data: FieldMessageDataMap,
            meta_data: MessageMetaData
    ) -> None:
        self._protocol = protocol
        self._data = data
        self._meta_data = meta_data

    @property
    def protocol(self) -> ProtocolMetaData:
        return self._protocol

    @property
    def data(self) -> FieldMessageDataMap:
        return self._data

    @property
    def meta_data(self) -> MessageMetaData:
        return self._meta_data

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
