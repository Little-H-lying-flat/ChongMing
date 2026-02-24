import sqlite3

def fix_db(db_path):
    print(f"Checking {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='executions';")
        if not cursor.fetchone():
            print("  Table 'executions' not found.")
            return

        print("  Table 'executions' found. Checking columns...")
        cursor.execute("PRAGMA table_info(executions);")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'environment_id' not in columns:
            print("  'environment_id' column missing. Altering table...")
            cursor.execute("ALTER TABLE executions ADD COLUMN environment_id VARCHAR(50);")
            conn.commit()
            print("  Success: Added environment_id column.")
        else:
            print("  'environment_id' already exists.")
            
    except Exception as e:
        print("  Error:", e)
    finally:
        conn.close()

if __name__ == '__main__':
    for db in ['chongming.db', 'test_platform.db', 'test.db']:
        fix_db(db)
