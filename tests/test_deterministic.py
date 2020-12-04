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
Deterministic tests of signature parsing and calculation.
"""

# isort: STDLIB
import unittest

# isort: THIRDPARTY
import dbus

# isort: LOCAL
from into_dbus_python import signature, xformer
from into_dbus_python._errors import IntoDPSignatureError, IntoDPUnexpectedValueError


class ParseTestCase(unittest.TestCase):
    """
    Test parsing various signatures.
    """

    def test_bad_array_value(self):
        """
        Verify that passing a dict for an array will raise an exception.
        """
        with self.assertRaises(IntoDPUnexpectedValueError):
            xformer("a(qq)")([dict()])

    def test_bad_base_case_value(self):
        """
        Verify that transforming a string to a numeric value will raise an
        exception.
        """
        with self.assertRaises(IntoDPUnexpectedValueError):
            xformer("x")(["string"])

    def test_variant_depth(self):
        """
        Verify that a nested variant has appropriate variant depth.
        """
        self.assertEqual(
            xformer("v")([("v", ("v", ("b", False)))])[0],
            dbus.Boolean(False, variant_level=3),
        )
        self.assertEqual(
            xformer("v")([("v", ("ab", [False]))])[0],
            dbus.Array([dbus.Boolean(False)], signature="b", variant_level=2),
        )
        self.assertEqual(
            xformer("av")([([("v", ("b", False))])])[0],
            dbus.Array([dbus.Boolean(False, variant_level=2)], signature="v"),
        )
        self.assertEqual(
            xformer("a{bv}")([{True: ("b", False)}])[0],
            dbus.Dictionary({dbus.Boolean(True): dbus.Boolean(False, variant_level=1)}),
        )
        self.assertEqual(
            xformer("(bv)")([(True, ("b", False))])[0],
            dbus.Struct([dbus.Boolean(True), dbus.Boolean(False, variant_level=1)]),
        )
        self.assertEqual(
            xformer("(bv)")([(True, ("v", ("b", True)))])[0],
            dbus.Struct(
                [dbus.Boolean(True), dbus.Boolean(True, variant_level=2)],
                signature="bv",
                variant_level=0,
            ),
        )


class SignatureTestCase(unittest.TestCase):
    """
    Tests for the signature method.
    """

    def test_exceptions(self):
        """
        Test that exceptions are properly raised.
        """
        with self.assertRaises(IntoDPSignatureError):
            signature(
                dbus.Array(
                    [dbus.Boolean(False, variant_level=2), dbus.Byte(0)], signature="v"
                )
            )

        with self.assertRaises(IntoDPSignatureError):
            signature("w")

        with self.assertRaises(IntoDPSignatureError):

            class TestObject:
                """
                A test  object that resembles a dbus-python object in having
                a variant_level field, but isn't actually a dbus-python
                object.
                """

                # pylint: disable=too-few-public-methods
                variant_level = 0

            signature(TestObject())
