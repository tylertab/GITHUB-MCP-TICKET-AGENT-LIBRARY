import sys, pathlib
# Ensure "src" is importable for tests (works locally and in CI)
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))
