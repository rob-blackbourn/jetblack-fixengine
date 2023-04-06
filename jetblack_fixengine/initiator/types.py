"""Types"""

from abc import ABCMeta
from ssl import SSLContext
from typing import Optional

from jetblack_fixparser.meta_data import ProtocolMetaData

from ..types import FIXEngine, Store


class AbstractInitiatorEngine(FIXEngine, metaclass=ABCMeta):
    """The interface for an initiator"""


class InitiatorConfig:

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
            logon_timeout: int = 60,
            heartbeat_timeout: int = 30,
            shutdown_timeout: float = 10.0,
            heartbeat_threshold: int = 1
    ) -> None:
        self.host = host
        self.port = port
        self.protocol = protocol
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.store = store
        self.logon_timeout = logon_timeout
        self.heartbeat_timeout = heartbeat_timeout
        self.ssl = ssl
        self.shutdown_timeout = shutdown_timeout
        self.heartbeat_threshold = heartbeat_threshold
