import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix broken list syntax: json_schema_extra={"example": ["A"}, "B"]) -> json_schema_extra={"example": ["A", "B"]}
    # Fix broken dict syntax: json_schema_extra={"example": {"K": "V"}, "B": "C"}) -> json_schema_extra={"example": {"K": "V", "B": "C"}}
    
    # 既然正则容易出问题，而且只有少部分被改坏了，我们写死几个具体的错误修复：
    replacements = [
        # executions.py
        (r'json_schema_extra={"example": \["TC-001"\}, "TC-002"\]\)', r'json_schema_extra={"example": ["TC-001", "TC-002"]})'),
        # left_pupil.py
        (r'json_schema_extra={"example": \{"Authorization": "Bearer \$\{token\}"\}\)', r'json_schema_extra={"example": {"Authorization": "Bearer ${token}"}})'),
        (r'json_schema_extra={"example": \{"name": "test_user"\}\)', r'json_schema_extra={"example": {"name": "test_user"}})'),
        (r'json_schema_extra={"example": \{"page": "1"\}\)', r'json_schema_extra={"example": {"page": "1"}})'),
        (r'json_schema_extra={"example": \{"\$\.code": 0\}\)', r'json_schema_extra={"example": {"$.code": 0}})'),
        (r'json_schema_extra={"example": \{"user_token": "\$\.data\.token"\}\)', r'json_schema_extra={"example": {"user_token": "$.data.token"}})'),
        # neural_design/models.py
        (r'json_schema_extra={"example": \{"Content-Type": "application/json"\}\)', r'json_schema_extra={"example": {"Content-Type": "application/json"}})'),
        (r'json_schema_extra={"example": \{"username": "admin"\}, "password": "\*\*\*"\}\)', r'json_schema_extra={"example": {"username": "admin", "password": "***"}})'),
        (r'json_schema_extra={"example": \{"page": "1"\}, "size": "10"\}\)', r'json_schema_extra={"example": {"page": "1", "size": "10"}})'),
        (r'json_schema_extra={"example": \{"\$\.data\.id": 123\}\)', r'json_schema_extra={"example": {"$.data.id": 123}})'),
    ]
    
    new_content = content
    for old, new in replacements:
        new_content = re.sub(old, new, new_content)
        
    if new_content != content:
        print(f"Fixed syntax errors in {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return 1
    return 0

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
