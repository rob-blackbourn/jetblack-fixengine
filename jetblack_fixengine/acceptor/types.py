"""Types"""

from abc import abstractmethod, ABCMeta
from datetime import datetime, time, tzinfo
from ssl import SSLContext
from typing import Optional, Tuple

from jetblack_fixparser.meta_data import ProtocolMetaData
from jetblack_fixparser.fix_message import SOH

from ..types import FIXEngine, Store


class AbstractAcceptorEngine(FIXEngine, metaclass=ABCMeta):
    """The interface for an acceptor"""

    @property
    @abstractmethod
    def logon_time_range(self) -> Optional[Tuple[time, time]]:
        """The logon time range"""

    @property
    @abstractmethod
    def logout_time(self) -> Optional[datetime]:
        """The logout time"""

    @logout_time.setter
    @abstractmethod
    def logout_time(self, value: datetime) -> None:
        """The logout time setter"""

    @property
    def tz(self) -> Optional[tzinfo]:
        """The time zone"""


class AcceptorConfig:

    def __init__(
            self,
            host: str,
            port: int,
            protocol: ProtocolMetaData,
            sender_comp_id: str,
            target_comp_id: str,
            store: Store,
            *,
            ssl: Optional[SSLContext] = None,
            client_shutdown_timeout: float = 10.0,
            sep: bytes = SOH,
            convert_sep_to_soh_for_checksum: bool = False,
            validate: bool = True,
            heartbeat_timeout: int = 30,
            heartbeat_threshold: int = 1,
            logon_time_range: Optional[Tuple[time, time]] = None,
            tz: Optional[tzinfo] = None
    ) -> None:
        self.host = host
        self.port = port
        self.protocol = protocol
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.store = store
        self.ssl = ssl
        self.client_shutdown_timeout = client_shutdown_timeout
        self.sep = sep
        self.convert_sep_to_soh_for_checksum = convert_sep_to_soh_for_checksum
        self.validate = validate
        self.heartbeat_timeout = heartbeat_timeout
        self.heartbeat_threshold = heartbeat_threshold
        self.logon_time_range = logon_time_range
        self.tz = tz
