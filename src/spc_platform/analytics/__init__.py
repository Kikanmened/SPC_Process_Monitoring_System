"""Analytics layer: the statistical core.

Pure functions over NumPy arrays. Imports ``domain`` and ``common`` only;
NumPy, SciPy, and statsmodels are permitted, and I/O of any kind is not
(SYSTEM_ARCHITECTURE.md §2, rule 2). Purity is what makes the statistical
test tier possible.
"""
