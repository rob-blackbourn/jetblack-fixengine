"""Types"""

from abc import ABCMeta

from ..types import FIXEngine


class AbstractInitiatorEngine(FIXEngine, metaclass=ABCMeta):
    """The interface for an initiator"""
