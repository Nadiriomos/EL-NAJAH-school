import sqlite3

def init_db():
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()

    # Students table
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            join_date TEXT NOT NULL DEFAULT (date('now'))
        )
    ''')

    # Groups table
    c.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    # Student-Group association
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_group (
            student_id INTEGER,
            group_id INTEGER,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(group_id) REFERENCES groups(id),
            PRIMARY KEY (student_id, group_id)
        )
    ''')

    # Payments table
    c.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            paid TEXT CHECK(paid IN ('paid', 'unpaid')) NOT NULL,
            payment_date TEXT NOT NULL,  -- store as YYYY-MM-DD
            UNIQUE(student_id, year, month),  -- only one payment record per student per month
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
    ''')


    conn.commit()
    conn.close()