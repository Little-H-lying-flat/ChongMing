import sqlite3

conn=sqlite3.connect('test.db')
c = conn.cursor()
c.execute("UPDATE environments SET base_url='http://127.0.0.1:8000/api/v1', name='Local Dev', is_default=1 WHERE base_url='2'")
conn.commit()
print("updated dummy environment")
