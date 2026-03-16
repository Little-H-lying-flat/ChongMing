import os

filepath = r'd:\project\ChongMing\backend\app\engines\right_pupil\__init__.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(1566, 1682):
    if i < len(lines):
        # 原本这里的缩进多出了 4 个空格（因为之前放进大的 try/except 没删掉）现在统统 -4
        if lines[i].startswith("                "):
             lines[i] = lines[i][4:]
        elif lines[i].startswith("    "):
             # Fallback
             pass

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Indentation fixed.")
