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


def _descending(dbus_object):
    """
    Verify levels of variant values always descend.

    :param object dbus_object: a dbus object
    :returns: None if there was a failure of the property, otherwise the level
    :rtype: int or NoneType

    None is a better choice than False, for 0, a valid variant level, is always
    interpreted as False.
    """
    # pylint: disable=too-many-return-statements
    if isinstance(dbus_object, dbus.Dictionary):
        key_levels = [_descending(x) for x in dbus_object.keys()]
        value_levels = [_descending(x) for x in dbus_object.values()]
        if any(k is None for k in key_levels) or any(v is None for v in value_levels):
            return None

        max_key_level = max(key_levels) if key_levels != [] else 0
        max_value_level = max(value_levels) if value_levels != [] else 0
        max_level = max(max_key_level, max_value_level)

        variant_level = dbus_object.variant_level
        if variant_level == 0:
            return max_level

        return None if variant_level < max_level + 1 else variant_level

    if isinstance(dbus_object, (dbus.Array, dbus.Struct)):
        levels = [_descending(x) for x in dbus_object]
        if any(l is None for l in levels):
            return None

        max_level = max(levels) if levels != [] else 0

        variant_level = dbus_object.variant_level
        if variant_level == 0:
            return max_level

        return None if variant_level < max_level + 1 else variant_level

    return dbus_object.variant_level


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
        Test that parsing is always succesful.

        Verify that the original signature corresponds to the signature
        returned by the parser and to the signature of the generated value.

        Verify that the variant levels always descend within the constructed
        value.
        """
        (a_signature, base_type_object) = strat

        (func, sig_synth) = xformers(a_signature)[0]
        (value, level) = func(base_type_object)
        sig_orig = dbus.Signature(a_signature)

        self.assertEqual(sig_orig, sig_synth)

        if "v" not in sig_orig:
            self.assertEqual(level, 0)
        self.assertIsNotNone(_descending(value))
        self.assertEqual(signature(value), sig_orig)

    @given(
        dbus_signatures(min_complete_types=1, blacklist="h")
        .map(lambda s: "(%s)" % s)
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
