"""FIX message factory"""

from aiofix.meta_data.message_member import MessageMemberMetaData
from datetime import datetime
from typing import Any, Mapping, Optional

from ..meta_data import ProtocolMetaData

from .fix_message import FixMessage, SOH


class FixMessageFactory:

    def __init__(
            self,
            protocol: ProtocolMetaData,
            sender_comp_id: str,
            target_comp_id: str,
            *,
            strict: bool = True,
            validate: bool = True,
            sep: bytes = SOH,
            convert_sep_for_checksum: bool = True,
            header_kwargs: Optional[Mapping[str, Any]] = None
    ) -> None:
        self.protocol = protocol
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.strict = strict
        self.validate = validate
        self.sep = sep
        self.convert_sep_for_checksum = convert_sep_for_checksum
        self.header_kwargs = header_kwargs

    def create(
            self,
            msg_type: str,
            msg_seq_num: int,
            sending_time: datetime,
            body_kwargs: Optional[Mapping[str, Any]] = None,
            header_kwargs: Optional[Mapping[str, Any]] = None,
            trailer_kwargs: Optional[Mapping[str, Any]] = None
    ) -> FixMessage:
        assert msg_type in self.protocol.fields_by_name['MsgType'].values_by_name

        header_args = {
            'BeginString': self.protocol.begin_string,
            'MsgType': msg_type,
            'MsgSeqNum': msg_seq_num,
            'SenderCompID': self.sender_comp_id,
            'TargetCompID': self.target_comp_id,
            'SendingTime': sending_time
        }
        if self.header_kwargs:
            header_args.update(self.header_kwargs)
        if header_kwargs:
            header_args.update(header_kwargs)

        data = {
            name: header_args[name]
            for name in self.protocol.header.keys()
            if name in header_args
        }

        if body_kwargs:
            data.update(body_kwargs)

        if trailer_kwargs:
            data.update({
                name: header_args[name]
                for name in self.protocol.trailer.keys()
                if name in trailer_kwargs
            })

        return FixMessage(self.protocol, data)

    def decode(self, message: bytes) -> FixMessage:
        return FixMessage.decode(
            self.protocol,
            message,
            strict=self.strict,
            validate=self.validate,
            sep=self.sep,
            convert_sep_for_checksum=self.convert_sep_for_checksum
        )
