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

# isort: STDLIB
from typing import Any

# isort: THIRDPARTY
import dbus

from ._errors import IntoDPSignatureError


def signature(dbus_object: Any, *, unpack=False) -> str:
    """
    Get the signature of a dbus object.

    :param dbus_object: the object
    :type dbus_object: a dbus object
    :param bool unpack: if True, unpack from enclosing variant type
    :returns: the corresponding signature
    :rtype: str
    """
    # pylint: disable=too-many-return-statements
    # pylint: disable=too-many-branches

    # The object passed may not be a dbus object, and consequently may not
    # have a variant_level attribute.
    if not hasattr(dbus_object, "variant_level"):
        raise IntoDPSignatureError(
            (
                "value does not have a variant_level attribute, "
                "can not determine the correct signature"
            ),
            dbus_object,
        )

    if dbus_object.variant_level != 0 and not unpack:
        return "v"

    if isinstance(dbus_object, dbus.Array):
        sigs = frozenset(signature(x) for x in dbus_object)
        len_sigs = len(sigs)
        if len_sigs > 1:
            raise IntoDPSignatureError(
                f"the dbus-python Array object {dbus_object} has items with varying signatures",
                dbus_object,
            )

        if len_sigs == 0:
            return "a" + dbus_object.signature

        return "a" + list(sigs)[0]

    if isinstance(dbus_object, dbus.Struct):
        sigs = (signature(x) for x in dbus_object)
        return "(" + "".join(x for x in sigs) + ")"

    if isinstance(dbus_object, dbus.Dictionary):
        key_sigs = frozenset(signature(x) for x in dbus_object.keys())
        value_sigs = frozenset(signature(x) for x in dbus_object.values())

        len_key_sigs = len(key_sigs)
        len_value_sigs = len(value_sigs)

        if len_key_sigs != len_value_sigs:
            # It seems impossible to force a dbus-python Dictionary value
            # to have this property; the Dictionary constructor prevents it.
            raise IntoDPSignatureError(
                f"the dbus-python Dictionary object {dbus_object} "
                f"does not have a valid signature",
                dbus_object,
            )  # pragma: no cover

        if len_key_sigs > 1:
            # It seems impossible to force a dbus-python Dictionary value
            # to have this property; the Dictionary constructor prevents it.
            raise IntoDPSignatureError(
                f"the dbus-python Dictionary object {dbus_object} "
                f"has different signatures for different keys",
                dbus_object,
            )  # pragma: no cover

        if len_key_sigs == 0:
            return "a{" + dbus_object.signature + "}"

        return "a{" + list(key_sigs)[0] + list(value_sigs)[0] + "}"

    if isinstance(dbus_object, dbus.Boolean):
        return "b"

    if isinstance(dbus_object, dbus.Byte):
        return "y"

    if isinstance(dbus_object, dbus.Double):
        return "d"

    if isinstance(dbus_object, dbus.Int16):
        return "n"

    if isinstance(dbus_object, dbus.Int32):
        return "i"

    if isinstance(dbus_object, dbus.Int64):
        return "x"

    if isinstance(dbus_object, dbus.ObjectPath):
        return "o"

    if isinstance(dbus_object, dbus.Signature):
        return "g"

    if isinstance(dbus_object, dbus.String):
        return "s"

    if isinstance(dbus_object, dbus.UInt16):
        return "q"

    if isinstance(dbus_object, dbus.UInt32):
        return "u"

    if isinstance(dbus_object, dbus.UInt64):
        return "t"

    if isinstance(dbus_object, dbus.types.UnixFd):  # pragma: no cover
        return "h"

    raise IntoDPSignatureError("object is not a dbus-python object type", dbus_object)
