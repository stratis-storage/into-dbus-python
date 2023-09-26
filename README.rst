A transformer to dbus-python types
==================================

Facilities for converting an object that inhabits core Python types, e.g.,
lists, ints, dicts, to an object that inhabits dbus-python types, e.g.,
dbus.Array, dbus.UInt32, dbus.Dictionary based on a specified dbus signature.

Motivation
----------

The dbus-python library is a library of python bindings for libdbus. It does
not provide facilities to ensure that the types of the values that client code
places on the D-Bus conform to the required signature. The client code may
either be a D-Bus service, so that the values that it places on the D-Bus
should conform to the signature that it specifies, or, in some cases, a client
of the service, which must conform to the specifications of the service.

If a service implements the Introspectable interface on its objects,
dbus-python will use the signature information to massage client messages
into the correct dbus types. If the Introspectable interface is unavailable,
dbus-python will guess the signature by recursively examining the values of
the arguments, and will then proceed the same as before. If the signature
contains a 'v', indicating a variant type, dbus-python must guess the type
of the corresponding value. dbus-python can be instructed not to make use of
dbus introspection by setting the introspect parameter to false in the
appropriate methods.

This library provides facilities to ensure that values placed on the D-Bus
conform to a given signature, by wrapping the values in the appropriate
constructors for this signature. It generates correct functions for any
valid signature.

Usage and Implementation Hints
------------------------------

Usage of the library is fairly straightforward::

   >>> from into_dbus_python import xformers
   >>> funcs = xformers("adq")
   >>> len(funcs)
   2

Note that the length of the list of functions is the same as the number of
complete types in the signature. Each element in the list of functions is
a tuple. ::

    >>> funcs[0]
    (<function ToDbusXformer._handleArray.<locals>.the_func at 0x7f4542f2d730>, 'ad')

The first element is the function itself, the second is a string which
matches the complete type signature for which this function yields values of
the correct type. Applying this function yields the actual value ::

    >>> funcs[0][0]([2.3, 37.5])
    (dbus.Array([dbus.Double(2.3), dbus.Double(37.5)], signature=dbus.Signature('d')), 0)

In this example, the signature was "ad" so the resulting value is a dbus.Array
of dbus.Double objects. The signature parameter has the appropriate value;
it is just 'd', the symbol for the type of the elements in the array,
double. Note that the function also yields a tuple, the converted value and
an int, which represents the variant level. Since there was no "v" in the
signature, the variant level is 0.

The generated functions will fail with an IntoDPError if passed invalid
arguments. ::

    >>> try:
    ...     funcs[0][0](True)
    ... except IntoDPError as err:
    ...     print("bad arg")
    ...
    bad arg

If any of the functions raises an exception that is not a subtype of
IntoDPError this constitutes a bug and is not part of the public API.

Conveniences
------------
The parser itself returns a list of tuples, of which generally only the first
element in the tuple is of interest to the client. The second element, the
string matched, is a necessary result for the recursive implementation,
but is not generally useful to the client. The resulting functions each
return a tuple of the transformed value and the variant level, generally only
the transformed value is of interest to the client.

For this reason, the library provides a convenience function, xformer(),
which takes a signature and returns a function, which takes a list of objects
and returns the list, transformed to appropriate dbus types. It can be used
in the following way::

    >>> from into_dbus_python import xformer
    >>> func = xformer("adq")
    >>> func([[2.3, 34.0], 3])
    [dbus.Array([dbus.Double(2.3), dbus.Double(34.0)], signature=dbus.Signature('d')), dbus.UInt16(3)]

Note that the function must take a list of values, one for each complete type
in the signature. Here, there are two complete types "ad", and "q", and there
are two resulting values.

If the signature contains a "v", for a variant type, the value must be a pair
of a signature and a value that inhabits that type. For example, ::

    >>> func = xformer("v")
    >>> func([("aq", [0, 1])])
    [dbus.Array([dbus.UInt16(0), dbus.UInt16(1)], signature=dbus.Signature('q'), variant_level=1)]

Note that the variant level of the constructed Array object is 1. A non-zero
variant level in the dbus object indicates that the object is a variant.
In this example the variant level is just 1. Further nesting of variants is
permitted, the variant level increases by one with each level. ::

    >>> func([("av", [("q", 0)])])
    [dbus.Array([dbus.UInt16(0, variant_level=1)], signature=dbus.Signature('v'), variant_level=2)]

Here the variant level of the variant element in the array, 0, is 1, but the
variant level of the whole array is 2, since the array inhabits a variant type
and contains a variant element.

Restrictions on Core Types
--------------------------
The generated functions place as few restrictions as possible on the types
of the values to be transformed. Generally speaking, a tuple is as good as a
list, since both are iterable. ::

    >>> func = xformer("adq")
    >>> func([(2.3, 34.0), 3])
    [dbus.Array([dbus.Double(2.3), dbus.Double(34.0)], signature=dbus.Signature('d')), dbus.UInt16(3)]

However, the inhabitant of a dbus.Dictionary type must be an object with an
items() method which yields pairs of keys and values, e.g., a dict.

The signature() function
------------------------
This library also exposes a function, signature(), which, given a value in
dbus-python types, calculates its signature. It has the following relation
to the xformer() function.

Let S be a signature. Let C be a list of values in Python core types.
Let V = xformer(S)(C). Then "".join(signature(v) for v in V) is equal to S.

Technical Remarks
-----------------

This package extends the parser for dbus signatures implemented in the
dbus-signature-pyparsing package
(https://github.com/stratis-storage/dbus-signature-pyparsing)
by adding actions to the individual parsers using the setParseAction() method.

The package has undergone significant testing using the Hypothesis testing
library (http://hypothesis.works/) and the external Hypothesis strategy
implemented in the hs-dbus-signature package
(https://github.com/stratis-storage/hs-dbus-signature).

Downstream packagers, if incorporating testing into their packaging, are
encouraged to use only the tests in the test_deterministic.py module, to
avoid testing failures that may arise due to the non-deterministic behavior
of Hypothesis tests.
