"""Keyed random streams: named, reproducible, and independent of draw order."""

from __future__ import annotations

import numpy as np

from spc_platform.simulation.seeds import derive_generator, derive_uuid_namespace_key


def test_same_key_and_seed_give_the_same_draws() -> None:
    first = derive_generator(42, "wafer_effect", "POLY_CD", 7).normal(size=16)
    second = derive_generator(42, "wafer_effect", "POLY_CD", 7).normal(size=16)

    np.testing.assert_array_equal(first, second)


def test_different_keys_give_unrelated_draws() -> None:
    left = derive_generator(42, "wafer_effect", "POLY_CD", 7).normal(size=512)
    right = derive_generator(42, "wafer_effect", "POLY_CD", 8).normal(size=512)

    assert not np.array_equal(left, right)
    # Independence, not merely inequality: two streams that were correlated
    # would leak structure between lots that the variance model says are
    # unrelated.
    assert abs(float(np.corrcoef(left, right)[0, 1])) < 0.15


def test_different_seeds_move_the_same_key() -> None:
    left = derive_generator(1, "lot_effect", "OXIDE_THK").normal(size=64)
    right = derive_generator(2, "lot_effect", "OXIDE_THK").normal(size=64)

    assert not np.array_equal(left, right)


def test_draws_do_not_depend_on_the_order_streams_are_created() -> None:
    """The property the whole module exists for: refactoring a loop is safe."""
    forwards = [derive_generator(9, "s", index).normal() for index in range(5)]
    backwards = [derive_generator(9, "s", index).normal() for index in reversed(range(5))]

    assert forwards == list(reversed(backwards))


def test_key_parts_are_separated_rather_than_concatenated() -> None:
    """``("a", "b")`` and ``("ab",)`` must not name the same stream.

    Under naive concatenation they would, silently coupling two entities the
    variance model treats as independent.
    """
    assert derive_uuid_namespace_key("a", "b") != derive_uuid_namespace_key("ab")
    assert not np.array_equal(
        derive_generator(3, "a", "b").normal(size=8),
        derive_generator(3, "ab").normal(size=8),
    )


def test_integer_and_string_parts_render_identically() -> None:
    """Documented behaviour: parts go through ``str``, so 1 and '1' are one key."""
    assert derive_uuid_namespace_key("a", 1) == derive_uuid_namespace_key("a", "1")
