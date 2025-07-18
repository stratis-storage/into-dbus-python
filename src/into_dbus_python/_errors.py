# Copyright 2016 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Error hierarchy for xformer generator.
"""
# isort: STDLIB
from typing import Any, Union

# isort: THIRDPARTY
from dbus import Array


class IntoDPError(Exception):
    """
    Top-level error.
    """


class IntoDPGenerationError(IntoDPError):
    """
    Exception raised during generation of a function.
    """


class IntoDPImpossibleTokenError(IntoDPGenerationError):
    """
    Exception raised when an impossible token is encountered.
    This should never occur, because the parser should fail.
    """


class IntoDPRuntimeError(IntoDPError):
    """
    Exception raised during execution of generated functions.
    """


class IntoDPUnexpectedValueError(IntoDPRuntimeError):
    """
    Exception raised when an unexpected value is encountered during a
    transformation.
    """

    def __init__(self, message: str, value: Any):
        """
        Initializer.

        :param str message: the message
        :param object value: the value encountered
        """
        super().__init__(message)
        self.value = value


class IntoDPSurprisingError(IntoDPRuntimeError):
    """
    Exception raised when a surprising error is caught during a transformation.
    Surprising errors can arise due to undocumented or incorrectly documented
    behaviors of dependent libraries or bugs in this library or dependent
    libraries.
    """

    def __init__(self, message, value):  # pragma: no cover
        """
        Initializer.

        :param str message: the message
        :param object value: the value encountered
        """
        super().__init__(message)
        self.value = value


class IntoDPSignatureError(IntoDPError):
    """
    Exception raised when a value does not seem to have a valid signature.
    """

    def __init__(self, message: str, value: Union[str, Array]):
        """
        Initializer.

        :param str message: the message
        :param object value: the problematic putative dbus-python object
        """
        super().__init__(message)
        self.value = value
