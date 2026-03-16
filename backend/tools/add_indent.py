import os

filepath = r'd:\project\ChongMing\backend\app\engines\right_pupil\__init__.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# add 4 spaces from 1494 to 1680 (0-indexed 1494 - 1680)
for i in range(1494, 1681):
    if i < len(lines):
        if lines[i].strip() == "":
            lines[i] = "\n"
        else:
            lines[i] = "    " + lines[i]

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Indentation added.")
