import sys
import pytest


if __name__ == "__main__":
    # Run the small set of handler tests
    sys.exit(pytest.main(["-q", "tests/test_greet_and_suggest.py", "tests/test_browse_categories.py", "tests/test_browse_select_and_products.py", "tests/test_select_product.py"]))
