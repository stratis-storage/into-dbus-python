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
Test signature parsing.
"""

import string
import unittest

import dbus

from dbus_signature_pyparsing import Parser

from hypothesis import given
from hypothesis import settings
from hypothesis import strategies

from hs_dbus_signature import dbus_signatures

from into_dbus_python import xformer
from into_dbus_python import xformers
from into_dbus_python import signature
from into_dbus_python import IntoDPError

# Omits h, unix fd, because it is unclear what are valid fds for dbus
SIGNATURE_STRATEGY = dbus_signatures(max_codes=20, blacklist="h")

OBJECT_PATH_STRATEGY = strategies.one_of(
   strategies.builds(
      '/'.__add__,
      strategies.builds(
         '/'.join,
         strategies.lists(
            strategies.text(
               alphabet=[
                  x for x in \
                     string.digits + \
                     string.ascii_uppercase + \
                     string.ascii_lowercase + \
                     '_'
               ],
               min_size=1,
               max_size=10
            ),
            max_size=10
         )
      )
   )
)


class StrategyGenerator(Parser):
    """
    Generate a hypothesis strategy for generating objects for a particular
    dbus signature which make use of base Python classes.
    """
    # pylint: disable=too-few-public-methods

    @staticmethod
    def _handleArray(toks):
        """
        Generate the correct strategy for an array signature.

        :param toks: the list of parsed tokens
        :returns: strategy that generates an array or dict as appropriate
        :rtype: strategy
        """

        if len(toks) == 5 and toks[1] == '{' and toks[4] == '}':
            return strategies.dictionaries(keys=toks[2], values=toks[3], max_size=20)
        elif len(toks) == 2:
            return strategies.lists(elements=toks[1], max_size=20)
        else: # pragma: no cover
            raise ValueError("unexpected tokens")

    def __init__(self):
        super(StrategyGenerator, self).__init__()

        # pylint: disable=unnecessary-lambda
        self.BYTE.setParseAction(
           lambda: strategies.integers(min_value=0, max_value=255)
        )
        self.BOOLEAN.setParseAction(lambda: strategies.booleans())
        self.INT16.setParseAction(
           lambda: strategies.integers(min_value=-0x8000, max_value=0x7fff)
        )
        self.UINT16.setParseAction(
           lambda: strategies.integers(min_value=0, max_value=0xffff)
        )
        self.INT32.setParseAction(
           lambda: strategies.integers(
              min_value=-0x80000000,
              max_value=0x7fffffff
           )
        )
        self.UINT32.setParseAction(
           lambda: strategies.integers(min_value=0, max_value=0xffffffff)
        )
        self.INT64.setParseAction(
           lambda: strategies.integers(
              min_value=-0x8000000000000000,
              max_value=0x7fffffffffffffff
           )
        )
        self.UINT64.setParseAction(
           lambda: strategies.integers(
              min_value=0,
              max_value=0xffffffffffffffff
           )
        )
        self.DOUBLE.setParseAction(lambda: strategies.floats())

        self.STRING.setParseAction(lambda: strategies.text())
        self.OBJECT_PATH.setParseAction(lambda: OBJECT_PATH_STRATEGY)
        self.SIGNATURE.setParseAction(lambda: SIGNATURE_STRATEGY)

        def _handleVariant():
            """
            Generate the correct strategy for a variant signature.

            :returns: strategy that generates an object that inhabits a variant
            :rtype: strategy
            """
            signature_strategy = dbus_signatures(
               max_codes=5,
               min_complete_types=1,
               max_complete_types=1,
               blacklist="h"
            )
            return signature_strategy.flatmap(
               lambda x: strategies.tuples(
                  strategies.just(x),
                  self.COMPLETE.parseString(x)[0]
               )
            )

        self.VARIANT.setParseAction(_handleVariant)

        self.ARRAY.setParseAction(StrategyGenerator._handleArray)

        self.STRUCT.setParseAction(
           # pylint: disable=used-before-assignment
           lambda toks: strategies.tuples(*toks[1:-1])
        )

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
        if any(k is None for k in key_levels) or \
           any(v is None for v in value_levels):
            return None

        max_key_level = max(key_levels) if key_levels != [] else 0
        max_value_level = max(value_levels) if value_levels != [] else 0
        max_level = max(max_key_level, max_value_level)

        variant_level = dbus_object.variant_level
        if variant_level == 0:
            return max_level

        if variant_level < max_level + 1:
            return None
        else:
            return variant_level
    elif isinstance(dbus_object, (dbus.Array, dbus.Struct)):
        levels = [_descending(x) for x in dbus_object]
        if any(l is None for l in levels):
            return None

        max_level = max(levels) if levels != [] else 0

        variant_level = dbus_object.variant_level
        if variant_level == 0:
            return max_level

        if variant_level < max_level + 1:
            return None
        else:
            return variant_level
    else:
        return dbus_object.variant_level


class ParseTestCase(unittest.TestCase):
    """
    Test parsing various signatures.
    """

    @given(SIGNATURE_STRATEGY)
    @settings(max_examples=100)
    def testParsing(self, a_signature):
        """
        Test that parsing is always succesful.

        Verify that the original signature corresponds to the signature
        returned by the parser and to the signature of the generated value.

        Verify that the variant levels always descend within the constructed
        value.
        """
        base_type_objects = [
           x.example() for x in \
              STRATEGY_GENERATOR.parseString(a_signature, parseAll=True)
        ]
        results = xformers(a_signature)
        funcs = [f for (f, _) in results]
        sigs = [s for (_, s) in results]

        results = [f(x) for (f, x) in zip(funcs, base_type_objects)]
        values = [v for (v, _) in results]
        levels = [l for (_, l) in results]

        for sig_orig, (sig_synth, (level, value)) in \
           zip(dbus.Signature(a_signature), zip(sigs, zip(levels, values))):
            self.assertEqual(sig_orig, sig_synth)
            if 'v' not in sig_orig:
                self.assertEqual(level, 0)
            self.assertIsNotNone(_descending(value))
            self.assertEqual(signature(value), sig_orig)

        pairs = \
           zip(
              dbus.Signature(a_signature),
              xformer(a_signature)(base_type_objects)
           )
        # test equality of signatures, rather than results, since nan != nan
        for sig, value in pairs:
            self.assertEqual(sig, signature(value))

    @given(
       dbus_signatures(min_complete_types=1, blacklist="h"). \
          map(lambda x: "(%s)" % x)
    )
    @settings(max_examples=10)
    def testStruct(self, sig):
        """
        Test exception throwing on a struct signature when number of items
        is not equal to number of complete types in struct signature.
        """
        struct = \
           [x.example() for x in \
              STRATEGY_GENERATOR.parseString(sig, parseAll=True)][0]

        xform = xformer(sig)

        with self.assertRaises(IntoDPError):
            xform([struct + (1, )])

        with self.assertRaises(IntoDPError):
            xform([struct[:-1]])

    @given(dbus_signatures(blacklist="hbs", exclude_dicts=True))
    @settings(max_examples=100)
    def testExceptions(self, sig):
        """
        Test that an exception is raised for a dict if '{' is blacklisted.

        Need to also blacklist 'b' and 's', since dbus.String and dbus.Boolean
        constructors can both convert a dict.
        """

        xform = xformer(sig)

        with self.assertRaises(IntoDPError):
            xform([{True: True}])

    def testBadArrayValue(self):
        """
        Verify that passing a dict for an array will raise an exception.
        """
        with self.assertRaises(IntoDPError):
            xformer('a(qq)')([dict()])

    def testVariantDepth(self):
        """
        Verify that a nested variant has appropriate variant depth.
        """
        self.assertEqual(
           xformer('v')([('v', ('v', ('b', False)))])[0].variant_level,
           3
        )
        self.assertEqual(
           xformer('v')([('v', ('ab', [False]))])[0],
           dbus.Array([dbus.Boolean(False)], signature='b', variant_level=2)
        )
        self.assertEqual(
           xformer('av')([([('v', ('b', False))])])[0],
           dbus.Array([dbus.Boolean(False, variant_level=2)], signature="v")
        )

    @given(STRATEGY_GENERATOR.parseString('v', parseAll=True)[0])
    @settings(max_examples=50)
    def testUnpacking(self, value):
        """
        Test that signature unpacking works.
        """
        dbus_value = xformer('v')([value])[0]
        unpacked = signature(dbus_value, unpack=True)
        packed = signature(dbus_value)

        self.assertEqual(packed, 'v')
        self.assertFalse(unpacked.startswith('v'))
