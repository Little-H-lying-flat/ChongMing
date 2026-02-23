import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to match Field(..., example=value)
    # It handles string literals, numbers, dicts, lists, booleans, and None
    # \1 is everything before 'example='
    # \2 is the value of 'example'
    # \3 is everything after the value (like a closing parenthesis or comma)
    pattern = re.compile(r'(Field\([^)]*?),\s*example\s*=\s*(.+?)([,\)])')
    
    def replacer(match):
        prefix = match.group(1)
        value = match.group(2).strip()
        suffix = match.group(3)
        return f'{prefix}, json_schema_extra={{"example": {value}}}{suffix}'

    new_content, count = pattern.subn(replacer, content)
    
    if count > 0:
        print(f"Fixed {count} occurrences in {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
    return count

def main():
    app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app')
    total_fixes = 0
    for root, _, files in os.walk(app_dir):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                total_fixes += process_file(filepath)
    print(f"Total fixes applied: {total_fixes}")

if __name__ == '__main__':
    main()
