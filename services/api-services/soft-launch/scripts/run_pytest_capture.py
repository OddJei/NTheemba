import sys
import argparse
import io
from contextlib import redirect_stdout, redirect_stderr
import pytest


def main():
    p = argparse.ArgumentParser(description="Run pytest and capture output to a file")
    p.add_argument("paths", nargs="*", default=["services/affiliate-engine/tests"], help="pytest paths")
    p.add_argument("-o", "--out", default="pytest_affiliate_output_direct.txt", help="output file")
    p.add_argument("--pytest-args", nargs=argparse.REMAINDER, default=[], help="additional pytest args (prefix with --pytest-args)")
    args = p.parse_args()

    buf = io.StringIO()
    exit_code = 0
    with redirect_stdout(buf), redirect_stderr(buf):
        exit_code = pytest.main(args.paths + args.pytest_args)

    out = buf.getvalue()
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out)

    print(f"Wrote pytest output to {args.out}; exit_code={exit_code}")
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
