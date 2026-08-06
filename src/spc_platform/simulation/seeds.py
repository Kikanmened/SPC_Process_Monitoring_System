"""Random streams derived from names rather than from draw order.

A dataset must reproduce byte for byte from its configuration and seed
(DATASET_GUIDE.md §4.4). The usual approach — one generator threaded through
the run and consumed as the loops happen to reach it — satisfies that only
until someone reorders a loop, at which point every value downstream of the
change moves and the ground truth silently stops describing the data.

Deriving each stream from a hash of the entity it belongs to removes that
coupling and buys two properties worth having:

* **Order independence.** Refactoring the traversal cannot change the output.
* **Locality.** Adding a lot, parameter, or fault leaves every other stream
  untouched, so a dataset extends without invalidating what came before.
"""

from __future__ import annotations

import hashlib

import numpy as np

_DIGEST_BYTES = 16
_WORD_BYTES = 4
_KEY_SEPARATOR = "\x1f"


def _key_words(key: tuple[object, ...]) -> list[int]:
    """Hash a stream key into 32-bit words for ``SeedSequence``."""
    canonical = _KEY_SEPARATOR.join(str(part) for part in key)
    digest = hashlib.blake2b(canonical.encode("utf-8"), digest_size=_DIGEST_BYTES).digest()
    return [
        int.from_bytes(digest[offset : offset + _WORD_BYTES], "big")
        for offset in range(0, _DIGEST_BYTES, _WORD_BYTES)
    ]


def derive_generator(master_seed: int, *key: object) -> np.random.Generator:
    """Return the random generator for one named stream.

    Parameters
    ----------
    master_seed
        The dataset seed. Changing it moves every stream together.
    *key
        The name of the stream, as the parts that identify it — for example
        ``("wafer_effect", parameter_id, product_id, lot_index)``. Parts are
        rendered with ``str`` and joined, so distinct keys must differ as text.

    Returns
    -------
    numpy.random.Generator
        A generator independent of every other key's generator.
    """
    sequence = np.random.SeedSequence([master_seed, *_key_words(key)])
    return np.random.default_rng(sequence)


def derive_uuid_namespace_key(*key: object) -> str:
    """Return the canonical text form of a key, for deterministic identifiers.

    Measurement identifiers are UUIDv5 over this text, so that a regenerated
    dataset carries the same keys as the one it reproduces.
    """
    return _KEY_SEPARATOR.join(str(part) for part in key)
