import sqlite3

conn = sqlite3.connect("audible.db")
c = conn.cursor()
c.execute("UPDATE workflows SET name=? WHERE id=2", ("Bridget - Real Estate Customer Support",))
conn.commit()

c.execute("SELECT id, name, released_definition_id, status FROM workflows")
for row in c.fetchall():
    print("Row:", row)
conn.close()
