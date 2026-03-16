import os
import sys

filepath = r'd:\project\ChongMing\backend\app\engines\right_pupil\__init__.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if 1568 <= i <= 1680:
        # We need these to be inside the `while step_count < self.max_steps:` loop.
        # The loop starts at line 1400: `while step_count < self.max_steps:` (indent: 12 spaces)
        # So contents inside should be 16 spaces.
        # Let's count current leading spaces:
        leading = len(line) - len(line.lstrip())
        content = line.lstrip()
        
        if content.strip() == "":
             new_lines.append("\n")
             continue
             
        # "action = self._correct_action_type(action, prompt)" requires 20 spaces
        if "action = self._correct_action_type" in content:
             new_lines.append(" " * 20 + content)
        elif content.startswith("if not action:") or content.startswith("if action.action_type == \"done\":"):
             new_lines.append(" " * 16 + content)
        elif content.startswith("break") and leading < 16:
             # The breaks for `if not action` and `if action.action_type == "done"`
             new_lines.append(" " * 20 + content)
        elif content.startswith("# 3. Execution") or content.startswith("max_retries") or content.startswith("retry_count =") or content.startswith("step_success") or content.startswith("while retry_count"):
             new_lines.append(" " * 16 + content)
        elif content.startswith("success = await self.runner") or content.startswith("if success:") or content.startswith("else:") or content.startswith("if not step_success:"):
             new_lines.append(" " * 20 + content)
        elif "history.append" in content and leading < 24 and not "step_success" in content:
             new_lines.append(" " * 24 + content)
        elif content.startswith("step_success = True") or content.startswith("break") and leading < 24:
             new_lines.append(" " * 24 + content)
        elif content.startswith("logger.") and leading < 24:
             new_lines.append(" " * 24 + content)
        elif content.startswith("retry_count += 1"):
             new_lines.append(" " * 24 + content)
        elif content.startswith("finally:"):
             new_lines.append(" " * 8 + content) # Matches original try
        elif content.startswith("return logs"):
             new_lines.append(" " * 8 + content)
        else:
             # if indent is severely broken (e.g. 12 spaces when it should be 16 or 20 inside while retry_count...)
             if leading < 16 and not content.startswith("except"):
                 new_lines.append(" " * 16 + content)
             else:
                 new_lines.append(line)
    else:
        new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Formatting attempted.")
