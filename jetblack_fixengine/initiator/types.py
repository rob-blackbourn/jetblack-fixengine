"""Types"""

from abc import ABCMeta

from ..types import FIXWorker


class AbstractInitiator(FIXWorker, metaclass=ABCMeta):
    """The interface for an initiator"""
