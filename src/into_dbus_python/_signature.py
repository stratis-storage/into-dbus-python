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
Definition of signature method.
"""

import dbus

from ._errors import IntoDPValueError


def signature(dbus_object, strip_variant_levels=0):
    """
    Get the signature of a dbus object.

    :param dbus_object: the object
    :type dbus_object: a dbus object
    :param strip_variant_levels: depth to which to strip variant levels
    :type strip_variant_levels: int
    :returns: the corresponding signature
    :rtype: str

    Default for strip_variant_levels is 0, indicating strip no levels.
    A negative value will cause no levels to be stripped.
    A positive value of n will cause n levels to be stripped.

    If it is impossible to substitute a stripped value for an unstripped value,
    as if there is an empty array with elements of variant type, the value
    will not be stripped.
    """
    # pylint: disable=too-many-return-statements
    # pylint: disable=too-many-branches

    variant_level = dbus_object.variant_level
    if variant_level != 0:
        if strip_variant_levels < variant_level:
            return 'v'
        else:
            strip_variant_levels = strip_variant_levels - variant_level

    if isinstance(dbus_object, dbus.Array):
        sigs = \
           frozenset(signature(x, strip_variant_levels) for x in dbus_object)
        len_sigs = len(sigs)
        if len_sigs > 1: # pragma: no cover
            raise IntoDPValueError(
               dbus_object,
               "dbus_object",
               "has bad signature"
            )

        if len_sigs == 0:
            return 'a' + dbus_object.signature

        return 'a' + [x for x in sigs][0]

    if isinstance(dbus_object, dbus.Struct):
        sigs = (signature(x, strip_variant_levels) for x in dbus_object)
        return '(' + "".join(x for x in sigs) + ')'

    if isinstance(dbus_object, dbus.Dictionary):
        key_sigs = \
           frozenset(signature(x, strip_variant_levels) \
           for x in dbus_object.keys())
        value_sigs = \
           frozenset(signature(x, strip_variant_levels) \
           for x in dbus_object.values())

        len_key_sigs = len(key_sigs)
        len_value_sigs = len(value_sigs)

        if len_key_sigs != len_value_sigs: # pragma: no cover
            raise IntoDPValueError(
               dbus_object,
               "dbus_object",
               "has bad signature"
            )

        if len_key_sigs > 1: # pragma: no cover
            raise IntoDPValueError(
               dbus_object,
               "dbus_object",
               "has bad signature"
            )

        if len_key_sigs == 0:
            return 'a{' + dbus_object.signature + '}'

        return 'a{' + [x for x in key_sigs][0] + [x for x in value_sigs][0] + '}'

    if isinstance(dbus_object, dbus.Boolean):
        return 'b'

    elif isinstance(dbus_object, dbus.Byte):
        return 'y'

    elif isinstance(dbus_object, dbus.Double):
        return 'd'

    elif isinstance(dbus_object, dbus.Int16):
        return 'n'

    elif isinstance(dbus_object, dbus.Int32):
        return 'i'

    elif isinstance(dbus_object, dbus.Int64):
        return 'x'

    elif isinstance(dbus_object, dbus.ObjectPath):
        return 'o'

    elif isinstance(dbus_object, dbus.Signature):
        return 'g'

    elif isinstance(dbus_object, dbus.String):
        return 's'

    elif isinstance(dbus_object, dbus.UInt16):
        return 'q'

    elif isinstance(dbus_object, dbus.UInt32):
        return 'u'

    elif isinstance(dbus_object, dbus.UInt64):
        return 't'

    elif isinstance(dbus_object, dbus.types.UnixFd): # pragma: no cover
        return 'h'
