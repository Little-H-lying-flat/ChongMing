import subprocess
import os

print("Starting tests...")
with open("e2e_report_safe.txt", "w", encoding="utf-8") as f:
    subprocess.run(["python", os.path.join("tests", "e2e", "test_right_pupil_e2e_timing.py")], stdout=f, stderr=subprocess.STDOUT)
print("Finished tests.")
