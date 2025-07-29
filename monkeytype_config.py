"""
Monkeytype Configuration File
"""

# isort: STDLIB
from typing import Any, Union

# isort: THIRDPARTY
from monkeytype.config import DefaultConfig
from monkeytype.typing import (
    ChainedRewriter,
    RemoveEmptyContainers,
    RewriteConfigDict,
    RewriteGenerator,
    RewriteLargeUnion,
    TypeRewriter,
)


class CanonicalizeUnionElementOrder(TypeRewriter):
    """
    Monkeytype type rewriter to sort union elements in canonical order.
    """

    @staticmethod
    def type_order(typ) -> str:
        """
        Return a value to be used as a key for sorting.
        """

        print(f"BIG: {typ}", flush=True)
        if typ is Any:
            return "Any"

        try:
            under_name = typ._name  # pylint: disable=protected-access
        except AttributeError:
            under_name = None

        try:
            dunder_name = typ.__name__
        except AttributeError:
            dunder_name = None

        return (
            under_name
            if under_name is not None
            else (dunder_name if dunder_name is not None else "")
        )

    def rewrite_Union(self, union):
        return Union[
            tuple(
                sorted(
                    list(union.__args__),
                    key=CanonicalizeUnionElementOrder.type_order,
                )
            )
        ]


class MyConfig(DefaultConfig):
    """
    Monkeytype configuration for this project
    """

    def type_rewriter(self):
        return ChainedRewriter(
            (
                RemoveEmptyContainers(),
                RewriteConfigDict(),
                RewriteLargeUnion(),
                RewriteGenerator(),
                CanonicalizeUnionElementOrder(),
            )
        )


CONFIG = MyConfig()
