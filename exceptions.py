"""
异常类
"""


class CustomException(Exception):
    """
    异常类
    """

    def __init__(self, message="BPOD Exception.", e=None):
        super().__init__(message)
        self.message = message
        self.e = e


class ConcurrencyException(Exception):
    """
    异常类
    """

    def __init__(self, message="BPOD ConcurrencyException.", e=None):
        super().__init__(message)
        self.message = message
        self.e = e
