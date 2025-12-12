#!/usr/bin/env python3
import os
import shutil
import subprocess
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
CONTIKI = THIS_DIR.parents[1]
COOJA_DIR = CONTIKI / "tools" / "cooja"
CSC = THIS_DIR / "cooja_dataset.csc"

LOG_DIR = THIS_DIR / "logs"
DATA_DIR = THIS_DIR / "datasets"
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

ATTACK_SCENARIOS = [
    ("normal",      0, 10),
    ("sinkhole",    1, 5),
    ("rank",        2, 5),
    ("blackhole",   3, 5),
    ("sel_forward", 4, 5),
    ("sybil",       5, 5),
    ("jamming",     6, 5),
    ("spoofing",    7, 5),
]

def run_cooja_once(label, run_idx):
    print("[+] Running scenario=%s run=%d" % (label, run_idx))

    testlog = COOJA_DIR / "build" / "COOJA.testlog"
    if testlog.exists():
        testlog.unlink()

    cmd = ["./cooja_nogui.sh", str(CSC)]
    subprocess.check_call(cmd, cwd=COOJA_DIR)

    if not testlog.exists():
        raise RuntimeError("COOJA.testlog not found; check cooja_nogui.sh")

    out_log = LOG_DIR / ("%s_run%d.log" % (label, run_idx))
    shutil.copy(testlog, out_log)
    print("    Saved log:", out_log)
    return out_log

def parse_log_to_csv(log_path, out_csv):
    env = os.environ.copy()
    env["DATASET_LOG_FILE"] = str(log_path)
    env["DATASET_OUT_FILE"] = str(out_csv)

    subprocess.check_call(
        ["python3", "parse_cooja_log.py"],
        cwd=THIS_DIR,
        env=env,
    )

def main():
    print("Contiki root:", CONTIKI)
    print("Cooja dir   :", COOJA_DIR)
    print("CSC file    :", CSC)

    if not CSC.exists():
        print("ERROR: cooja_dataset.csc not found in", THIS_DIR)
        return

    for label, atk_type, runs in ATTACK_SCENARIOS:
        print("\n=== Scenario '%s' (ATTACK_TYPE=%d) runs=%d ===" % (label, atk_type, runs))
        print("NOTE: Make sure the motes in the CSC use firmware compiled")
        print("      with ATTACK_TYPE=%d for this scenario.\n" % atk_type)

        for r in range(1, runs + 1):
            log_path = run_cooja_once(label, r)
            out_csv = DATA_DIR / ("%s_run%d.csv" % (label, r))
            parse_log_to_csv(log_path, out_csv)

    print("\nAll runs completed. CSVs are in:", DATA_DIR)

if __name__ == "__main__":
    main()
