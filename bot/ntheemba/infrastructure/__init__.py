"""Infrastructure adapter package.

Concrete Redis and PostgreSQL adapters are intentionally imported from their
respective subpackages only when the configured runtime requires them. Keeping
this package initializer side-effect free prevents an optional production
backend from becoming an import-time dependency of memory-only tests and local
composition.
"""

__all__: list[str] = []
