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
Error heirarchy for xformer generator.
"""


class IntoDPError(Exception):
    """
    Top-level error.
    """
    pass


class IntoDPGenerationError(IntoDPError):
    """
    Raised when there was a failure to generate a transformer method from
    a signature.
    """
    pass


class IntoDPParseError(IntoDPGenerationError):
    """
    Raised when there was a failure to parse the signature.
    """
    _FMT_STR = "failed to parse signature %s"

    def __init__(self, signature, msg=None):  # pragma: no cover
        """
        Initializer.

        :param str signature: the D-Bus signature
        :param str msg: an explanatory message
        """
        # pylint: disable=super-init-not-called
        self._signature = signature
        self._msg = msg

    def __str__(self):  # pragma: no cover
        if self._msg:
            fmt_str = self._FMT_STR + ": %s"
            return fmt_str % (self._signature, self._msg)
        return self._FMT_STR % self._signature


class IntoDPValueError(IntoDPError):
    """ Raised when a parameter has an unacceptable value.

        May also be raised when the parameter has an unacceptable type.
    """
    _FMT_STR = "value '%s' for parameter %s is unacceptable"

    def __init__(self, value, param, msg=None):  # pragma: no cover
        """ Initializer.

            :param object value: the value
            :param str param: the parameter
            :param str msg: an explanatory message
        """
        # pylint: disable=super-init-not-called
        self._value = value
        self._param = param
        self._msg = msg

    def __str__(self):  # pragma: no cover
        if self._msg:
            fmt_str = self._FMT_STR + ": %s"
            return fmt_str % (self._value, self._param, self._msg)
        return self._FMT_STR % (self._value, self._param)
