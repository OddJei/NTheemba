def test_pytest_sanity():
    # Repo root pytest intentionally does not run per-service unit tests.
    # Those suites should be executed within each service directory.
    assert True
