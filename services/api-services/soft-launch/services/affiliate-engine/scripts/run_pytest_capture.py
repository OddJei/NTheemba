import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / "pytest_output.txt"
args = [sys.executable, "-m", "pytest", "-q"]
# Run in service root so tests import local package
print("Running:", " ".join(args), "in", str(root))
proc = subprocess.Popen(args, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
stdout, _ = proc.communicate()
text = stdout.decode("utf-8", errors="replace")
with open(out, "w", encoding="utf-8") as f:
    f.write(text)
print(f"Wrote pytest output to {out}")
sys.exit(proc.returncode)
