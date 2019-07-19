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
Transforming Python basic types to Python dbus types.
"""

import functools

import dbus

from dbus_signature_pyparsing import Parser

from ._errors import IntoDPError
from ._errors import IntoDPImpossibleTokenError
from ._errors import IntoDPSurprisingError
from ._errors import IntoDPUnexpectedValueError


def _wrapper(func):
    """
    Wraps a generated function so that it catches all unexpected errors and
    raises IntoDPSurprisingErrors.

    :param func: the transforming function
    """

    @functools.wraps(func)
    def the_func(expr):
        """
        The actual function.

        :param object expr: the expression to be xformed to dbus-python types
        """
        try:
            return func(expr)
        # Allow KeyboardInterrupt error to be propagated
        except KeyboardInterrupt as err:  # pragma: no cover
            raise err
        except IntoDPError as err:
            raise err
        except BaseException as err:
            raise IntoDPSurprisingError(
                "encountered a surprising error while transforming some expression",
                expr) from err

    return the_func


class _ToDbusXformer(Parser):
    """
    Class which extends a Parser to yield a function that yields
    a function that transforms a value in base Python types to a correct value
    using dbus-python types.

    Actually, it yields a pair, a function and a signature string. The
    signature string is useful for stowing a signature in Array or Dictionary
    types, as may be necessary if the Array or Dictionary is empty, and so
    the type can not be inferred from the contents of the value.
    """
    # pylint: disable=too-few-public-methods

    @staticmethod
    def _variant_levels(level, variant):
        """
        Gets the level for the variant.

        :param int level: the current variant level
        :param int variant: the value for this level if variant

        :returns: a level for the object and one for the function
        :rtype: int * int
        """
        return (level + variant, level + variant) \
           if variant != 0 else (variant, level)

    def _handle_variant(self):
        """
        Generate the correct function for a variant signature.

        :returns: function that returns an appropriate value
        :rtype: ((str * object) or list)-> object
        """

        def the_func(a_tuple, variant=0):
            """
            Function for generating a variant value from a tuple.

            :param a_tuple: the parts of the variant
            :type a_tuple: (str * object) or list
            :param int variant: object's variant index
            :returns: a value of the correct type with correct variant level
            :rtype: object * int
            """
            (signature, an_obj) = a_tuple
            (func, sig) = self.COMPLETE.parseString(signature)[0]
            assert sig == signature
            (xformed, _) = func(an_obj, variant=variant + 1)
            return (xformed, xformed.variant_level)

        return (the_func, 'v')

    @staticmethod
    def _handle_array(toks):
        """
        Generate the correct function for an array signature.

        :param toks: the list of parsed tokens
        :returns: function that returns an Array or Dictionary value
        :rtype: ((or list dict) -> ((or Array Dictionary) * int)) * str
        """

        if len(toks) == 5 and toks[1] == '{' and toks[4] == '}':
            subtree = toks[2:4]
            signature = ''.join(s for (_, s) in subtree)
            [key_func, value_func] = [f for (f, _) in subtree]

            def the_dict_func(a_dict, variant=0):
                """
                Function for generating a Dictionary from a dict.

                :param a_dict: the dictionary to transform
                :type a_dict: dict of (`a * `b)
                :param int variant: variant level

                :returns: a dbus dictionary of transformed values and level
                :rtype: Dictionary * int
                """
                elements = \
                   [(key_func(x), value_func(y)) for (x, y) in a_dict.items()]
                level = 0 if elements == [] \
                   else max(max(x, y) for ((_, x), (_, y)) in elements)
                (obj_level, func_level) = \
                   _ToDbusXformer._variant_levels(level, variant)
                return (dbus.types.Dictionary(
                    ((x, y) for ((x, _), (y, _)) in elements),
                    signature=signature,
                    variant_level=obj_level), func_level)

            return (the_dict_func, 'a{' + signature + '}')

        if len(toks) == 2:
            (func, sig) = toks[1]

            def the_array_func(a_list, variant=0):
                """
                Function for generating an Array from a list.

                :param a_list: the list to transform
                :type a_list: list of `a
                :param int variant: variant level of the value
                :returns: a dbus Array of transformed values and variant level
                :rtype: Array * int
                """
                if isinstance(a_list, dict):
                    raise IntoDPUnexpectedValueError(
                        "expected a list for an array but found a dict: %s" %
                        a_list, a_list)
                elements = [func(x) for x in a_list]
                level = 0 if elements == [] else max(x for (_, x) in elements)
                (obj_level, func_level) = \
                   _ToDbusXformer._variant_levels(level, variant)

                return (dbus.types.Array(
                    (x for (x, _) in elements),
                    signature=sig,
                    variant_level=obj_level), func_level)

            return (the_array_func, 'a' + sig)

        raise IntoDPImpossibleTokenError("Encountered unexpected tokens in the token stream") \
                # pragma: no cover

    @staticmethod
    def _handle_struct(toks):
        """
        Generate the correct function for a struct signature.

        :param toks: the list of parsed tokens
        :returns: function that returns an Array or Dictionary value
        :rtype: ((list or tuple) -> (Struct * int)) * str
        """
        subtrees = toks[1:-1]
        signature = ''.join(s for (_, s) in subtrees)
        funcs = [f for (f, _) in subtrees]

        def the_func(a_list, variant=0):
            """
            Function for generating a Struct from a list.

            :param a_list: the list to transform
            :type a_list: list or tuple
            :param int variant: variant index
            :returns: a dbus Struct of transformed values and variant level
            :rtype: Struct * int
            :raises IntoDPRuntimeError:
            """
            if isinstance(a_list, dict):
                raise IntoDPUnexpectedValueError(
                    "expected a simple sequence for the fields of a struct but found a dict: %s"
                    % a_list, a_list)
            if len(a_list) != len(funcs):
                raise IntoDPUnexpectedValueError(
                    "expected %u elements for a struct, but found %u" %
                    (len(funcs), len(a_list)), a_list)
            elements = [f(x) for (f, x) in zip(funcs, a_list)]
            level = 0 if elements == [] else max(x for (_, x) in elements)
            (obj_level, func_level) = \
                _ToDbusXformer._variant_levels(level, variant)
            return (dbus.types.Struct(
                (x for (x, _) in elements),
                signature=signature,
                variant_level=obj_level), func_level)

        return (the_func, '(' + signature + ')')

    @staticmethod
    def _handle_base_case(klass, symbol):
        """
        Handle a base case.

        :param type klass: the class constructor
        :param str symbol: the type code
        """

        def the_func(value, variant=0):
            """
            Base case.

            :param int variant: variant level for this object
            :returns: a tuple of a dbus object and the variant level
            :rtype: dbus object * int
            """
            (obj_level, func_level) = _ToDbusXformer._variant_levels(
                0, variant)
            return (klass(value, variant_level=obj_level), func_level)

        return lambda: (the_func, symbol)

    def __init__(self):
        super(_ToDbusXformer, self).__init__()

        self.BYTE.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.Byte, 'y'))
        self.BOOLEAN.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.Boolean, 'b'))
        self.INT16.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.Int16, 'n'))
        self.UINT16.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.UInt16, 'q'))
        self.INT32.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.Int32, 'i'))
        self.UINT32.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.UInt32, 'u'))
        self.INT64.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.Int64, 'x'))
        self.UINT64.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.UInt64, 't'))
        self.DOUBLE.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.Double, 'd'))
        self.UNIX_FD.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.UnixFd, 'h'))
        self.STRING.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.String, 's'))
        self.OBJECT_PATH.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.ObjectPath, 'o'))
        self.SIGNATURE.setParseAction(
            _ToDbusXformer._handle_base_case(dbus.types.Signature, 'g'))

        self.VARIANT.setParseAction(self._handle_variant)

        self.ARRAY.setParseAction(_ToDbusXformer._handle_array)

        self.STRUCT.setParseAction(_ToDbusXformer._handle_struct)


_XFORMER = _ToDbusXformer()


def xformers(sig):
    """
    Get the list of xformer functions for the given signature.

    :param str sig: a signature
    :returns: a list of xformer functions for the given signature.
    :rtype: list of tuple of a function * str
    """
    return \
       [(_wrapper(f), l) for (f, l) in \
       _XFORMER.PARSER.parseString(sig, parseAll=True)]


def xformer(signature):
    """
    Returns a transformer function for the given signature.

    :param str signature: a dbus signature
    :returns: a function to transform a list of objects to inhabit the signature
    :rtype: (list of object) -> (list of object)
    """

    funcs = [f for (f, _) in xformers(signature)]

    def the_func(objects):
        """
        Returns the a list of objects, transformed.

        :param objects: a list of objects
        :type objects: list of object

        :returns: transformed objects
        :rtype: list of object (in dbus types)
        """
        if len(objects) != len(funcs):
            raise IntoDPUnexpectedValueError(
                "expected %u items to transform but found %u" % (len(funcs),
                                                                 len(objects)),
                objects)
        return [x for (x, _) in (f(a) for (f, a) in zip(funcs, objects))]

    return the_func
