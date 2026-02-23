import sqlite3
import json

conn = sqlite3.connect('test.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

for exec_id in ['EXEC_5992459A', 'EXEC_BFA68707']:
    print(f"--- Execution {exec_id} ---")
    cur.execute("SELECT * FROM execution_steps WHERE execution_id=?", (exec_id,))
    steps = cur.fetchall()
    for step in steps:
        step_dict = dict(step)
        print(f"  Step ID: {step_dict.get('id')}")
        print(f"    Status: {step_dict.get('status')}")
        if step_dict.get('error_msg'):
            print(f"    Error: {step_dict.get('error_msg')}")
        if step_dict.get('response_data'):
            try:
                data = json.loads(step_dict['response_data'])
                print(f"    Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            except:
                pass
    
conn.close()
