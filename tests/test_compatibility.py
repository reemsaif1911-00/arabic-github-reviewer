import subprocess
import sys


def test_direct_cli_repair_smoke(tmp_path):
    (tmp_path / "sample.py").write_text("value = xrange(2)\n", encoding="utf-8")
    completed = subprocess.run([sys.executable, "reviewer/main.py", str(tmp_path), "--repair", "--format", "json"], capture_output=True, text=True)
    assert completed.returncode == 0
    assert '"repairs"' in completed.stdout
    assert "range(2)" in completed.stdout
