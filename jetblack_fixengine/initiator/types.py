"""Types"""

from abc import ABCMeta

from ..types import FIXApplication


class AbstractInitiator(FIXApplication, metaclass=ABCMeta):
    """The interface for an initiator"""
