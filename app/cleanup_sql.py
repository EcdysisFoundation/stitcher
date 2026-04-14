import sqlite3

#################################################################
### Run ad hoc SQL in Docker like
### docker exec -u 0 -it <container_name_or_id> python app/cleanup_sql.py
#################################################################

DB_PATH = '/sqlite_data/database.db'

# Connect to your database file
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Example: clear out depricated field
    sql = "UPDATE UploadFileModel SET predictions = NULL WHERE predictions is not NULL"
    cursor.execute(sql)

    # Commit the changes!
    conn.commit()
    print(f"Cleanup successful. Rows affected: {cursor.rowcount}")
except Exception as e:
    conn.rollback()
    print(f"An error occurred: {e}")
finally:
    conn.close()
