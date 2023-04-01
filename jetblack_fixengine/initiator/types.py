"""Types"""

from abc import ABCMeta

from ..types import AbstractHandler


class AbstractInitiator(AbstractHandler, metaclass=ABCMeta):
    """The interface for an initiator"""
