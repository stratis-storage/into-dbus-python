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
Hypothesis-based tests of signature parsing and calculation.
"""

# isort: STDLIB
import string
import unittest
from os import sys

# isort: THIRDPARTY
import dbus
from hypothesis import HealthCheck, example, given, settings, strategies

# isort: FIRSTPARTY
from dbus_signature_pyparsing import Parser
from hs_dbus_signature import dbus_signatures

# isort: LOCAL
from into_dbus_python import signature, xformer, xformers
from into_dbus_python._errors import IntoDPUnexpectedValueError

settings.register_profile(
    "tracing", deadline=None, suppress_health_check=[HealthCheck.too_slow]
)
if sys.gettrace() is not None:
    settings.load_profile("tracing")

# Omits h, unix fd, because it is unclear what are valid fds for dbus
SIGNATURE_STRATEGY = dbus_signatures(max_codes=20, blacklist="h")

OBJECT_PATH_STRATEGY = strategies.builds(
    "/".__add__,
    strategies.builds(
        "/".join,
        strategies.lists(
            strategies.text(
                alphabet=list(
                    string.digits
                    + string.ascii_uppercase
                    + string.ascii_lowercase
                    + "_"
                ),
                min_size=1,
                max_size=10,
            ),
            max_size=10,
        ),
    ),
)


class StrategyGenerator(Parser):
    """
    Generate a hypothesis strategy for generating objects for a particular
    dbus signature which make use of base Python classes.
    """

    # pylint: disable=too-few-public-methods

    @staticmethod
    def _handle_array(toks):
        """
        Generate the correct strategy for an array signature.

        :param toks: the list of parsed tokens
        :returns: strategy that generates an array or dict as appropriate
        :rtype: strategy
        """

        if len(toks) == 5 and toks[1] == "{" and toks[4] == "}":
            return strategies.dictionaries(keys=toks[2], values=toks[3], max_size=20)
        if len(toks) == 2:
            return strategies.lists(elements=toks[1], max_size=20)
        raise ValueError("unexpected tokens")  # pragma: no cover

    def __init__(self):
        super().__init__()

        # pylint: disable=unnecessary-lambda
        self.BYTE.setParseAction(
            lambda: strategies.integers(min_value=0, max_value=255)
        )
        self.BOOLEAN.setParseAction(lambda: strategies.booleans())
        self.INT16.setParseAction(
            lambda: strategies.integers(min_value=-0x8000, max_value=0x7FFF)
        )
        self.UINT16.setParseAction(
            lambda: strategies.integers(min_value=0, max_value=0xFFFF)
        )
        self.INT32.setParseAction(
            lambda: strategies.integers(min_value=-0x80000000, max_value=0x7FFFFFFF)
        )
        self.UINT32.setParseAction(
            lambda: strategies.integers(min_value=0, max_value=0xFFFFFFFF)
        )
        self.INT64.setParseAction(
            lambda: strategies.integers(
                min_value=-0x8000000000000000, max_value=0x7FFFFFFFFFFFFFFF
            )
        )
        self.UINT64.setParseAction(
            lambda: strategies.integers(min_value=0, max_value=0xFFFFFFFFFFFFFFFF)
        )
        self.DOUBLE.setParseAction(lambda: strategies.floats())

        self.STRING.setParseAction(lambda: strategies.text())
        self.OBJECT_PATH.setParseAction(lambda: OBJECT_PATH_STRATEGY)
        self.SIGNATURE.setParseAction(lambda: SIGNATURE_STRATEGY)

        def _handle_variant():
            """
            Generate the correct strategy for a variant signature.

            :returns: strategy that generates an object that inhabits a variant
            :rtype: strategy
            """
            signature_strategy = dbus_signatures(
                max_codes=2,
                max_struct_len=2,
                min_complete_types=1,
                max_complete_types=1,
                blacklist="h",
            )
            return signature_strategy.flatmap(
                lambda x: strategies.tuples(
                    strategies.just(x), self.COMPLETE.parseString(x)[0]
                )
            )

        self.VARIANT.setParseAction(_handle_variant)

        self.ARRAY.setParseAction(StrategyGenerator._handle_array)

        self.STRUCT.setParseAction(lambda toks: strategies.tuples(*toks[1:-1]))


STRATEGY_GENERATOR = StrategyGenerator().PARSER


class ParseTestCase(unittest.TestCase):
    """
    Test parsing various signatures.
    """

    @given(
        dbus_signatures(
            min_complete_types=1, max_complete_types=1, blacklist="h"
        ).flatmap(
            lambda s: strategies.tuples(
                strategies.just(s), STRATEGY_GENERATOR.parseString(s, parseAll=True)[0]
            )
        )
    )
    @settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_parsing(self, strat):
        """
        Test that parsing is always successful.

        Verify that the original signature corresponds to the signature
        returned by the parser and to the signature of the generated value.

        Verify that the variant levels always descend within the constructed
        value.
        """
        (a_signature, base_type_object) = strat

        (func, sig_synth) = xformers(a_signature)[0]
        value = func(base_type_object)
        sig_orig = dbus.Signature(a_signature)

        self.assertEqual(sig_orig, sig_synth)

        self.assertEqual(signature(value), sig_orig)

    @given(
        dbus_signatures(min_complete_types=1, blacklist="h")
        .map(lambda s: f"({s})")
        .flatmap(
            lambda s: strategies.tuples(
                strategies.just(s), STRATEGY_GENERATOR.parseString(s, parseAll=True)[0]
            )
        )
    )
    @settings(
        max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None
    )
    def test_struct(self, strat):
        """
        Test exception throwing on a struct signature when number of items
        is not equal to number of complete types in struct signature.
        """
        (sig, struct) = strat

        xform = xformer(sig)

        with self.assertRaises(IntoDPUnexpectedValueError):
            xform([struct + (1,)])

        with self.assertRaises(IntoDPUnexpectedValueError):
            xform([struct[:-1]])

    @given(dbus_signatures(blacklist="hbs", exclude_dicts=True))
    @settings(max_examples=100)
    @example(sig="v")
    def test_exceptions(self, sig):
        """
        Test that an exception is raised for a dict if '{' is blacklisted.

        Need to also blacklist 'b' and 's', since dbus.String and dbus.Boolean
        constructors can both convert a dict.
        """

        xform = xformer(sig)

        with self.assertRaises(IntoDPUnexpectedValueError):
            xform([{True: True}])


class SignatureTestCase(unittest.TestCase):
    """
    Tests for the signature method.
    """

    @given(STRATEGY_GENERATOR.parseString("v", parseAll=True)[0])
    @settings(max_examples=50)
    def test_unpacking(self, value):
        """
        Test that signature unpacking works.
        """
        dbus_value = xformer("v")([value])[0]
        unpacked = signature(dbus_value, unpack=True)
        packed = signature(dbus_value)

        self.assertEqual(packed, "v")
        self.assertFalse(unpacked.startswith("v"))

    @given(OBJECT_PATH_STRATEGY.map(dbus.ObjectPath))
    @settings(max_examples=2)
    def test_object_path(self, value):
        """
        Test that the signature of an object path is "o".
        """
        self.assertEqual(signature(value), "o")

    @given(STRATEGY_GENERATOR.parseString("b", parseAll=True)[0].map(dbus.Boolean))
    @settings(max_examples=2)
    def test_boolean(self, value):
        """
        Test that the signature of a boolean type is "b".
        """
        self.assertEqual(signature(value), "b")

    @given(STRATEGY_GENERATOR.parseString("y", parseAll=True)[0].map(dbus.Byte))
    @settings(max_examples=2)
    def test_byte(self, value):
        """
        Test that the signature of a byte type is "y".
        """
        self.assertEqual(signature(value), "y")

    @given(STRATEGY_GENERATOR.parseString("d", parseAll=True)[0].map(dbus.Double))
    @settings(max_examples=2)
    def test_double(self, value):
        """
        Test that the signature of a double type is "d".
        """
        self.assertEqual(signature(value), "d")

    @given(STRATEGY_GENERATOR.parseString("n", parseAll=True)[0].map(dbus.Int16))
    @settings(max_examples=2)
    def test_int16(self, value):
        """
        Test that the signature of an int16 type is "n".
        """
        self.assertEqual(signature(value), "n")

    @given(STRATEGY_GENERATOR.parseString("i", parseAll=True)[0].map(dbus.Int32))
    @settings(max_examples=2)
    def test_int32(self, value):
        """
        Test that the signature of an int32 type is "i".
        """
        self.assertEqual(signature(value), "i")

    @given(STRATEGY_GENERATOR.parseString("x", parseAll=True)[0].map(dbus.Int64))
    @settings(max_examples=2)
    def test_int64(self, value):
        """
        Test that the signature of an int64 type is "x".
        """
        self.assertEqual(signature(value), "x")

    @given(STRATEGY_GENERATOR.parseString("g", parseAll=True)[0].map(dbus.Signature))
    @settings(max_examples=2)
    def test_signature(self, value):
        """
        Test that the signature of a signature type is "g".
        """
        self.assertEqual(signature(value), "g")

    @given(STRATEGY_GENERATOR.parseString("s", parseAll=True)[0].map(dbus.String))
    @settings(max_examples=2)
    def test_string(self, value):
        """
        Test that the signature of a string type is "s".
        """
        self.assertEqual(signature(value), "s")

    @given(STRATEGY_GENERATOR.parseString("q", parseAll=True)[0].map(dbus.UInt16))
    @settings(max_examples=2)
    def test_uint16(self, value):
        """
        Test that the signature of a uint16 type is "q".
        """
        self.assertEqual(signature(value), "q")

    @given(STRATEGY_GENERATOR.parseString("u", parseAll=True)[0].map(dbus.UInt32))
    @settings(max_examples=2)
    def test_uint32(self, value):
        """
        Test that the signature of a uint32 type is "u".
        """
        self.assertEqual(signature(value), "u")

    @given(STRATEGY_GENERATOR.parseString("t", parseAll=True)[0].map(dbus.UInt64))
    @settings(max_examples=2)
    def test_uint64(self, value):
        """
        Test that the signature of a uint64 type is "t".
        """
        self.assertEqual(signature(value), "t")
