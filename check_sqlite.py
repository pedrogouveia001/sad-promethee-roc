import sqlite3

conn = sqlite3.connect('instance/sad_promethee.db')
cursor = conn.cursor()

print("=== SQLITE DIRECT CHECK ===")
# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

for table in [t[0] for t in tables]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"Count of {table}: {count}")

# Check global_values
cursor.execute("SELECT DISTINCT period_date FROM global_values;")
dates = cursor.fetchall()
print("GlobalValue dates:", [d[0] for d in dates])

# Check statistical_results
cursor.execute("SELECT * FROM statistical_results;")
rows = cursor.fetchall()
print("Statistical results count:", len(rows))
for r in rows:
    print(r)

conn.close()
