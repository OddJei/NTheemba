import sys
import pytest

if __name__ == '__main__':
    # Run the two cycle handling tests
    args = [
        'tests/test_cycle_handling.py',
        'tests/test_cycle_resolution_integration.py',
        '-q',
    ]
    rc = pytest.main(args)
    print('\nPYTEST EXIT CODE:', rc)
    sys.exit(rc)
