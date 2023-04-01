"""Types"""

from abc import ABCMeta

from ..types import TransportHandler


class AbstractInitiator(TransportHandler, metaclass=ABCMeta):
    """The interface for an initiator"""
