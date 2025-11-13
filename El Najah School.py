import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, Menu, messagebox

import sqlite3
import os
import time
import sys

from datetime import datetime
from PIL import Image

from DB import init_db       # from DB.py
import menu_tools           # from menu_tools.py
import paymants_log         # from paymants_log.py

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
now = datetime.now()

init_db()  # Once per app launch
conn = sqlite3.connect("elnajah.db")
cursor = conn.cursor()    


# === Color Scheme ===
background = "#F4F7FA"
primary    = "#3B82F6"  # Blue-500
secondary  = "#60A5FA"  # Blue-400
text       = "#1F2937"  # Gray-800
hover      = "#DAD9E9"  # Blue-600

# === Main Window Setup ===
ElNajahSchool = ctk.CTk()
ElNajahSchool.title("El Najah School")
ElNajahSchool.geometry("1024x768")
ElNajahSchool.attributes('-fullscreen', True)
ElNajahSchool.configure(fg_color=background)
ElNajahSchool.bind("<Escape>", lambda event: ElNajahSchool.quit())


# === Menu Bar (still standard Tk) ===
from tkinter import Menu
menubar = Menu(ElNajahSchool)
file_menu = Menu(menubar, tearoff=0)
file_menu.add_command(label="Exit", command=ElNajahSchool.quit)
menubar.add_cascade(label="Menu", menu=file_menu)
ElNajahSchool.config(menu=menubar)

# === Tool Bar ===
tools_menu = Menu(menubar, tearoff=0)
tools_menu.add_command(
    label="Delete Groupless Students",
    command=menu_tools.delete_groupless_students
)
tools_menu.add_command(
    label="Merge Duplicate Students",
    command=menu_tools.merge_duplicate_students
)
tools_menu.add_command(
    label="Bulk Remove Group if Only Group",
    command=menu_tools.bulk_remove_group_if_only_group
)
menubar.add_cascade(label="Tools", menu=tools_menu)

# === Backup Bar ===
backup_menu = Menu(menubar, tearoff=0)
backup_menu.add_command(
    label="Backup Database",
    command=menu_tools.backup_database
)
backup_menu.add_command(
    label="Restore Database",
    command=menu_tools.restore_backup
)
backup_menu.add_command(
    label="Purge Old Backups",
    command=menu_tools.purge_old_backups
)
menubar.add_cascade(label="Backup", menu=backup_menu)

# === Exports Menu ===
Export_menu = Menu(menubar, tearoff=0)
Export_menu.add_command(
    label="Export Group to PDF",
    command=menu_tools.open_group_selector_and_export
)
Export_menu.add_command(
    label="Export All Students to Excel",
    command=menu_tools.export_all_students_excel
)
Export_menu.add_command(
    label="Export Unpaid Students to PDF",
    command=menu_tools.export_unpaid_students_pdf
)
Export_menu.add_command(
    label="Export Student Count to PDF",
    command=menu_tools.export_student_count_pdf
)
Export_menu.add_command(
    label="Export Student Payment History to PDF",
    command=menu_tools.export_student_payment_history_pdf
)
menubar.add_cascade(label="Export", menu=Export_menu)

# === Help Menu ===
help_menu = Menu(menubar, tearoff=0)
help_menu.add_command(
    label="Contact Support",
    command=menu_tools.contact_support
)
help_menu.add_command(
    label="Send Feedback",
    command=menu_tools.send_feedback
)
menubar.add_cascade(label="Help", menu=help_menu)


# === Welcome Label ===
logo_path = resource_path("El Najah School logo.png")
logo_img = ctk.CTkImage(
    light_image=Image.open(logo_path),
    dark_image=Image.open(logo_path),
    size=(615/1.8, 172/1.8)
)

# Display image in a label
label = ctk.CTkLabel(ElNajahSchool, image=logo_img, text="") 
label.pack(pady=5)

# === Top Frame for Buttons ===
frame = ctk.CTkFrame(ElNajahSchool, fg_color="transparent")
frame.pack(pady=0, padx=20, fill='x')

left_half = ctk.CTkFrame(frame, width=480, height=60, fg_color="transparent")
left_half.pack(side='left', fill='y', expand=True)
left_half.pack_propagate(False)

right_half = ctk.CTkFrame(frame, width=480, height=60, fg_color="transparent")
right_half.pack(side='left', fill='y', expand=True)
right_half.pack_propagate(False)

# === Add Student Popup ===
def open_add_student():
    top = ctk.CTkToplevel(ElNajahSchool)
    top.title("New Student Registration")
    top.geometry("500x700")
    top.lift()
    top.focus_force()
    top.grab_set()

    ctk.CTkLabel(top, text="Add new student", font=("Arial", 24)).pack(pady=20)

    # Wrap grid-based widgets in a frame
    add_student_frame = ctk.CTkFrame(top, fg_color="transparent")
    add_student_frame.pack(fill="both", expand=True, padx=20, pady=10)

    # make the main frame a single-column grid
    add_student_frame.grid_columnconfigure(0, weight=1)

    # === ID Field ===
    id_frame = ctk.CTkFrame(add_student_frame, fg_color="transparent")
    id_frame.grid(row=0, column=0, padx=10, pady=(0, 8), sticky="ew")
    id_frame.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(id_frame, text="ID:", font=("Arial", 18)).grid(row=0, column=0, padx=(0, 10), sticky="w")
    id_entry = ctk.CTkEntry(id_frame, font=("Arial", 18), justify='right')
    id_entry.grid(row=0, column=1, sticky="ew")

    # === Name Field ===
    name_frame = ctk.CTkFrame(add_student_frame, fg_color="transparent")
    name_frame.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
    name_frame.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(name_frame, text="Name:", font=("Arial", 18)).grid(row=0, column=0, padx=(0, 10), sticky="w")
    entry = ctk.CTkEntry(name_frame, font=("Arial", 18), justify='right')
    entry.grid(row=0, column=1, sticky="ew")

    # Payment Frame inside your Add Student window
    pay_frame = ctk.CTkFrame(add_student_frame, fg_color="transparent", height=200)
    pay_frame.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="nsew")
    pay_frame.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(pay_frame, text="Payment Information", font=("Arial", 20)).grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="w")

    # Year Entry
    ctk.CTkLabel(pay_frame, text="Year:", font=("Arial", 16)).grid(row=1, column=0, sticky="w")
    year_entry = ctk.CTkEntry(pay_frame, font=("Arial", 16), placeholder_text="YYYY")
    year_entry.grid(row=1, column=1, padx=10, pady=(0, 8), sticky="ew")

    # Month Selection
    ctk.CTkLabel(pay_frame, text="Month:", font=("Arial", 16)).grid(row=2, column=0, sticky="w")
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    month_var = ctk.StringVar(value=months[0])
    ctk.CTkOptionMenu(pay_frame, values=months, variable=month_var).grid(row=2, column=1, padx=10, pady=(0, 8), sticky="ew")

    # Paid / Unpaid Radio Buttons
    radio_var = ctk.StringVar(value="paid")
    ctk.CTkLabel(pay_frame, text="Payment Status:", font=("Arial", 16)).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 2))
    status_frame = ctk.CTkFrame(pay_frame, fg_color="transparent")
    status_frame.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 6))
    ctk.CTkRadioButton(status_frame, text="Paid", variable=radio_var, value="paid").grid(row=0, column=0, padx=6)
    ctk.CTkRadioButton(status_frame, text="Unpaid", variable=radio_var, value="unpaid").grid(row=0, column=1, padx=6)

    # Cancel button inside pay_frame (grid-consistent)
    

    # === Group Selection ===
    group_selection_frame = ctk.CTkFrame(add_student_frame, fg_color="transparent", height=200)
    group_selection_frame.grid(row=3, column=0, padx=10, pady=(0, 8), sticky="nsew")
    group_selection_frame.grid_columnconfigure(0, weight=1)
    group_selection_frame.grid_rowconfigure(1, weight=1)
    ctk.CTkLabel(group_selection_frame, text="Select Groups:", font=("Arial", 18)).grid(row=0, column=0, sticky="w", pady=(0,6))

    scrollable = ctk.CTkScrollableFrame(group_selection_frame, width=400, height=150, fg_color="white")
    scrollable.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

    group_vars = {}

    def reload_groups():
        # clear and repopulate checkboxes
        for widget in scrollable.winfo_children():
            widget.destroy()

        group_names = get_all_groups()  # Fetch from DB
        for name in group_names:
            var = ctk.BooleanVar(value=False)
            checkbox = ctk.CTkCheckBox(scrollable, text=name, variable=var)
            checkbox.pack(anchor="w", pady=2, padx=6)   # pack inside scrollable is fine
            group_vars[name] = var

    reload_groups()

    def handle_add_student():
        name = entry.get()
        # validate name (was missing)
        if not name.strip():
            messagebox.showerror("Invalid Name", "Student name is required.")
            return

        selected_groups = [g for g, v in group_vars.items() if v.get()]

        # Validate ID
        id_text = id_entry.get().strip()
        if not id_text:
            messagebox.showerror("Invalid ID", "Student ID is required.")
            return
        if not id_text.isdigit():
            messagebox.showerror("Invalid ID", "ID must be a number.")
            return
        manual_id = int(id_text)

        # Validate year
        year_text = year_entry.get().strip()
        if not year_text:
            messagebox.showerror("Invalid Year", "Year is required.")
            return
        if not year_text.isdigit():
            messagebox.showerror("Invalid Year", "Year must be a number.")
            return
        year = int(year_text)

        # Get month and pay status
        month = month_var.get()
        pay_status = radio_var.get()

        # Call updated add_student -> only close window on success
        success = add_student(name, pay_status, selected_groups, manual_id, year, month)
        if success:
            top.destroy()

    # Buttons frame (grid-consistent)
    buttons_frame = ctk.CTkFrame(group_selection_frame, fg_color="transparent")
    buttons_frame.grid(row=2, column=0, pady=(8,10), sticky="ew")
    buttons_frame.grid_columnconfigure(0, weight=1)
    buttons_frame.grid_columnconfigure(1, weight=1)

    ctk.CTkButton(buttons_frame, text="Add Student", command=handle_add_student).grid(row=0, column=0, padx=8, sticky="ew")
    ctk.CTkButton(buttons_frame, text="Cancel", command=top.destroy).grid(row=0, column=1, padx=8, sticky="ew")

def get_all_groups():
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("SELECT name FROM groups")
    groups = [row[0] for row in c.fetchall()]
    conn.close()
    return groups

def add_student(name, pay_status, selected_groups, manual_id, year, month):
    payment_date = datetime.now().strftime("%Y-%m-%d")
    join_date = datetime.now().strftime("%Y-%m-%d")  # new line

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    success = False

    try:
        # Check if ID exists
        c.execute("SELECT 1 FROM students WHERE id = ?", (manual_id,))
        if c.fetchone():
            messagebox.showerror("ID Exists", f"Student ID {manual_id} already exists.")
            return False

        # Insert student with join_date
        c.execute(
            "INSERT INTO students (id, name, join_date) VALUES (?, ?, ?)",
            (manual_id, name, join_date)
        )

        # Link to groups safely
        for group_name in selected_groups:
            c.execute("INSERT OR IGNORE INTO groups (name) VALUES (?)", (group_name,))
            c.execute("SELECT id FROM groups WHERE name = ?", (group_name,))
            row = c.fetchone()
            if row is None:
                raise Exception(f"Failed to retrieve ID for group '{group_name}'")
            group_id = row[0]
            c.execute(
                "INSERT OR IGNORE INTO student_group (student_id, group_id) VALUES (?, ?)",
                (manual_id, group_id)
            )

        # Insert payment safely
        month_number = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ].index(month) + 1

        c.execute('''
            INSERT OR IGNORE INTO payments (student_id, year, month, paid, payment_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (manual_id, year, month_number, pay_status, payment_date))

        conn.commit()
        success = True
        print(f"✅ Student '{name}' added with ID {manual_id} and payment for {month} {year}")
        messagebox.showinfo("Success", f"Student '{name}' added with payment for {month} {year}.")

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Error", str(e))
        success = False

    finally:
        conn.close()

    if success:
        refresh_treeview_all()  # only refresh if add worked

    return success

# === Add Group Popup ===
def open_add_group(reload_group_list=None):
    top = ctk.CTkToplevel(ElNajahSchool)
    top.title("New Group Registration")
    top.geometry("600x200")
    top.grab_set()
    top.focus_force()

    label = ctk.CTkLabel(top, text="Add / Delete Group", font=("Arial", 24))
    label.pack(pady=12)

    frame = ctk.CTkFrame(top, fg_color="transparent")
    frame.pack(pady=10, padx=20, fill='x')

    entry = ctk.CTkEntry(frame, font=("Arial", 18), justify='right')
    entry.pack(side='left', fill='x', expand=True)

    # Add handler
    def handle_add_group():
        name = entry.get().strip().capitalize()
        if not name:
            messagebox.showerror("Error", "Group name is required.")
            return

        success = add_group(name)  # assumes existing add_group returns True if created
        if success:
            messagebox.showinfo("Success", f"Group '{name}' added successfully.")
            if reload_group_list:
                reload_group_list()
            top.destroy()
        else:
            # add_group may already show info; still keep fallback
            messagebox.showinfo("Info", f"Group '{name}' already exists.")

    # Delete handler
    def handle_delete_group():
        name = entry.get().strip().capitalize()
        if not name:
            messagebox.showerror("Error", "Group name is required to delete.")
            return

        # confirm destructive action
        if not messagebox.askyesno("Confirm Delete", f"Delete group '{name}'?\nThis will remove the group from all students."):
            return

        ok = delete_group(name)
        if ok:
            messagebox.showinfo("Deleted", f"Group '{name}' deleted.")
            if reload_group_list:
                reload_group_list()
            top.destroy()
        else:
            messagebox.showinfo("Not found", f"Group '{name}' does not exist.")

    add_btn = ctk.CTkButton(frame, text="Add Group", command=handle_add_group)
    add_btn.pack(side='left', padx=8)

    del_btn = ctk.CTkButton(frame, text="Delete Group", fg_color="#FF3B30", command=handle_delete_group)
    del_btn.pack(side='left', padx=8)

def add_group(name):
    if not name.strip():
        messagebox.showerror("Error", "Group name cannot be empty.")
        return False

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()

    try:
        c.execute("INSERT INTO groups (name) VALUES (?)", (name.strip(),))
        conn.commit()
        print(f"✅ Group '{name}' added.")
        return True
    except sqlite3.IntegrityError:
        messagebox.showinfo("Already Exists", f"Group '{name}' already exists.")
        return False
    finally:
        conn.close()

def delete_group(name):
    """Delete group by name and all student_group links. Returns True on success, False if not found."""
    name = name.strip()
    if not name:
        messagebox.showerror("Error", "Group name is required.")
        return False

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        # check existence
        c.execute("SELECT id FROM groups WHERE name = ?", (name,))
        row = c.fetchone()
        if not row:
            return False

        group_id = row[0]

        # remove links in student_group first
        c.execute("DELETE FROM student_group WHERE group_id = ?", (group_id,))
        # remove the group itself
        c.execute("DELETE FROM groups WHERE id = ?", (group_id,))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        messagebox.showerror("DB Error", str(e))
        return False
    finally:
        conn.close()


# === Buttons ===
left_button = ctk.CTkButton(left_half, text="Add Student", font=("Arial", 16), command=open_add_student, fg_color=primary, text_color=text)
left_button.place(relx=0.5, rely=0.5, anchor="center")

right_button = ctk.CTkButton(right_half, text="Add Group", font=("Arial", 16), command=open_add_group, fg_color=primary, text_color=text)
right_button.place(relx=0.5, rely=0.5, anchor="center")


# === Search Frame ===
search_frame = ctk.CTkFrame(ElNajahSchool, fg_color="transparent")
search_frame.pack(pady=10, fill="x", padx=10)

frame = ctk.CTkFrame(search_frame, fg_color="transparent")
frame.pack(side="left", expand=True, fill="x", padx=5)



radio_var = ctk.StringVar(value="ID")
ctk.CTkRadioButton(frame, text="ID", variable=radio_var, value="ID").pack(side='left')
ctk.CTkRadioButton(frame, text="Name", variable=radio_var, value="Name").pack(side='left')

entry1_var = ctk.StringVar()
entry1 = ctk.CTkEntry(frame, textvariable=entry1_var, font=("Arial", 16), justify="right", fg_color=secondary, text_color=text)
entry1.pack(side="left", expand=True, fill="x")



def search_students(year=None, month=None):
    """
    Search students by ID or Name and show their payment status for the given month/year.
    If year/month is None, use current month/year.
    """
    from datetime import datetime

    search_type = radio_var.get()
    search_text = entry1_var.get().strip()

    if search_type not in ["ID", "Name"]:
        messagebox.showerror("Error", "Please select a search type.")
        return
    if not search_text:
        messagebox.showerror("Error", "Please enter search text.")
        return

    # Default to current month/year
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    sql = """
        SELECT s.id, s.name,
               COALESCE(GROUP_CONCAT(g.name), '—') AS groups,
               CASE
                   WHEN strftime('%Y-%m', ?) < strftime('%Y-%m', s.join_date) THEN 'No record'
                   WHEN p.paid = 'paid' THEN 'Paid (' || p.payment_date || ')'
                   WHEN p.paid = 'unpaid' THEN 'Unpaid'
                   ELSE 'Unpaid'
               END AS monthly_payment
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        LEFT JOIN payments p
            ON s.id = p.student_id
           AND p.year = ?
           AND p.month = ?
    """

    params = (f"{year}-{month:02d}-01", year, month)

    if search_type == "ID":
        sql += " WHERE s.id = ? GROUP BY s.id"
        params += (search_text,)
    else:  # Name search
        sql += " WHERE s.name LIKE ? GROUP BY s.id"
        params += ('%' + search_text + '%',)

    # Update Treeview
    _update_tree_from_query(sql, params)



button1 = ctk.CTkButton(frame, text="Search", command=search_students, font=("Arial", 16), fg_color=primary, text_color=text)
button1.pack(side="left", padx=(5, 0))

def fetch_student(student_id):
    """Return dict: {'id', 'name', 'pay', 'groups' (list)}
       pay is the status for the CURRENT month ('paid'|'unpaid') or None if no record.
    """
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        # basic student row
        c.execute("SELECT id, name FROM students WHERE id = ?", (student_id,))
        row = c.fetchone()
        if not row:
            return None
        sid, name = row

        # current month/year payment (if any)
        now = datetime.now()
        cy, cm = now.year, now.month
        c.execute("""
            SELECT paid FROM payments
            WHERE student_id = ? AND year = ? AND month = ?
            LIMIT 1
        """, (student_id, cy, cm))
        pr = c.fetchone()
        pay = pr[0] if pr else None

        # groups list
        c.execute("""
            SELECT g.name
            FROM groups g
            JOIN student_group sg ON g.id = sg.group_id
            WHERE sg.student_id = ?
            ORDER BY g.name
        """, (student_id,))
        groups = [r[0] for r in c.fetchall()]

        return {"id": sid, "name": name, "pay": pay, "groups": groups}
    finally:
        conn.close()

def update_student(student_id, name, pay_status, selected_groups):
    """
    Update student's name and reset group links.
    Also set payment status for the CURRENT month in payments table.
    Returns True on success, False on failure (and shows messagebox).
    """
    if not name.strip():
        messagebox.showerror("Validation", "Name is required.")
        return False

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        # Update student name
        c.execute("UPDATE students SET name = ? WHERE id = ?", (name.strip(), student_id))

        # Clear existing links
        c.execute("DELETE FROM student_group WHERE student_id = ?", (student_id,))

        # Ensure groups exist and link them
        for group_name in selected_groups:
            c.execute("INSERT OR IGNORE INTO groups (name) VALUES (?)", (group_name,))
            c.execute("SELECT id FROM groups WHERE name = ?", (group_name,))
            gid = c.fetchone()[0]
            c.execute("INSERT INTO student_group (student_id, group_id) VALUES (?, ?)", (student_id, gid))

        # Write payment for current month/year (insert or replace)
        now = datetime.now()
        cy, cm = now.year, now.month
        payment_date = now.strftime("%Y-%m-%d")

        # Use INSERT OR REPLACE so updating status for the same month overwrites previous
        c.execute("""
            INSERT INTO payments (student_id, year, month, paid, payment_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id, year, month) DO UPDATE SET
                paid=excluded.paid,
                payment_date=excluded.payment_date
        """, (student_id, cy, cm, pay_status, payment_date))

        conn.commit()

        # keep behavior consistent: refresh UI here and return success
        refresh_treeview_all()
        return True

    except Exception as e:
        conn.rollback()
        messagebox.showerror("DB Error", str(e))
        return False

    finally:
        conn.close()

def refresh_treeview_all(year=None, month=None):
    for i in tree.get_children():
        tree.delete(i)
    setup_tree_columns(tree)

    if year is None or month is None:
        from datetime import datetime
        now = datetime.now()
        year, month = now.year, now.month

    selected_date = f"{year}-{month:02d}-01"

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT s.id,
               s.name,
               COALESCE(GROUP_CONCAT(g.name), '—') AS groups,
               CASE
                   WHEN date(?) < date(s.join_date) THEN 'Unpaid'
                   WHEN p.paid = 'paid' THEN 'Paid'
                   ELSE 'Unpaid'
               END AS status
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON g.id = sg.group_id
        LEFT JOIN payments p
             ON s.id = p.student_id
            AND p.year = ? AND p.month = ?
        GROUP BY s.id
    """, (selected_date, year, month))

    for row in c.fetchall():
        tree.insert("", "end", values=row)

    conn.close()




def open_edit_student_modal(student_id):
    data = fetch_student(student_id)
    if not data:
        messagebox.showerror("Not found", f"Student ID {student_id} not found.")
        return

    top = ctk.CTkToplevel(ElNajahSchool)
    top.title(f"Edit Student — {student_id}")
    top.geometry("500x600")
    top.lift(); top.focus_force(); top.grab_set()

    # ID (disabled)
    id_frame = ctk.CTkFrame(top, fg_color="transparent")
    id_frame.pack(pady=8, padx=20, fill='x')
    ctk.CTkLabel(id_frame, text="ID:", font=("Arial", 14), width=80, anchor='e').pack(side='left')
    id_entry = ctk.CTkEntry(id_frame, font=("Arial", 14), justify='right')
    id_entry.pack(side='left', fill='x', expand=True)
    id_entry.insert(0, str(data["id"]))
    id_entry.configure(state="disabled")

    # Name
    name_frame = ctk.CTkFrame(top, fg_color="transparent")
    name_frame.pack(pady=8, padx=20, fill='x')
    ctk.CTkLabel(name_frame, text="Name:", font=("Arial", 14), width=80, anchor='e').pack(side='left')
    name_entry = ctk.CTkEntry(name_frame, font=("Arial", 14), justify='right')
    name_entry.pack(side='left', fill='x', expand=True)
    name_entry.insert(0, data["name"])

    # Pay radio
    pay_frame = ctk.CTkFrame(top, fg_color="transparent")
    pay_frame.pack(pady=8, padx=20, fill='x')
    ctk.CTkLabel(pay_frame, text="Pay:", font=("Arial", 14), width=80, anchor='e').pack(side='left')
    pay_var = ctk.StringVar(value=data["pay"] or "paid")
    rframe = ctk.CTkFrame(pay_frame, fg_color="transparent")
    rframe.pack(side='left', expand=True)
    ctk.CTkRadioButton(rframe, text="Paid", variable=pay_var, value="paid").pack(side='left', padx=6)
    ctk.CTkRadioButton(rframe, text="Unpaid", variable=pay_var, value="unpaid").pack(side='left', padx=6)

    # Groups (scrollable with prechecks)
    group_selection_frame = ctk.CTkFrame(top, fg_color="transparent")
    group_selection_frame.pack(pady=8, padx=20, fill='both', expand=True)
    ctk.CTkLabel(group_selection_frame, text="Groups:", font=("Arial", 14)).pack(anchor='w', pady=4)

    scrollable = ctk.CTkScrollableFrame(group_selection_frame, width=440, height=200, fg_color="white")
    scrollable.pack(fill='both', expand=False)

    # map name -> BooleanVar
    group_vars = {}
    all_groups = get_all_groups()  # existing groups in DB
    student_groups = set(data["groups"])

    for g in all_groups:
        var = ctk.BooleanVar(value=(g in student_groups))
        checkbox = ctk.CTkCheckBox(scrollable, text=g, variable=var)
        checkbox.pack(anchor="w", pady=2, padx=8)
        group_vars[g] = var

    # Buttons
    btn1_frame = ctk.CTkFrame(top, fg_color="transparent")
    btn1_frame.pack(pady=12, padx=20, fill='x')
    btn2_frame = ctk.CTkFrame(top, fg_color="transparent")
    btn2_frame.pack(pady=12, padx=20, fill='x')

    def save_and_close():
        new_name = name_entry.get().strip()
        new_pay = pay_var.get()
        selected = [g for g, v in group_vars.items() if v.get()]

        if not new_name:
            messagebox.showerror("Validation", "Name is required.")
            return

        ok = update_student(student_id, new_name, new_pay, selected)
        if ok:
            refresh_treeview_all()
            top.destroy()

    ctk.CTkButton(btn1_frame, text="Save", command=save_and_close).pack(padx=10)
    ctk.CTkButton(btn2_frame, text="Cancel", command=top.destroy).pack(padx=10)

def start_edit_selected():
    sel = tree.focus()
    if not sel:
        messagebox.showwarning("Selection", "Select a student to edit.")
        return
    student_id = tree.item(sel, "values")[0]
    open_edit_student_modal(int(student_id))

# button2 from your search frame
button2 = ctk.CTkButton(frame, text="Edit", font=("Arial", 16), fg_color="#43C24E", text_color=text)
button2.configure(command=start_edit_selected)
button2.pack(side="left", padx=(5, 0))


# keep a small last-deleted snapshot for undo
_last_deleted = None

def perform_delete(student_id):
    """
    Delete student and its links. Snapshot record to _last_deleted for possible undo.
    Returns True on success.
    """
    global _last_deleted
    data = fetch_student(student_id)
    if not data:
        messagebox.showerror("Error", f"Student ID {student_id} not found.")
        return False

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        # snapshot for undo
        _last_deleted = {
            "student": {"id": data["id"], "name": data["name"], "pay": data["pay"]},
            "groups": data["groups"][:]  # list copy
        }

        # remove links then student
        c.execute("DELETE FROM student_group WHERE student_id = ?", (student_id,))
        c.execute("DELETE FROM students WHERE id = ?", (student_id,))

        conn.commit()
        refresh_treeview_all()
        return True
    except Exception as e:
        conn.rollback()
        messagebox.showerror("DB Error", str(e))
        return False
    finally:
        conn.close()

def undo_delete():
    """Restore the last deleted student (if any)."""
    global _last_deleted
    if not _last_deleted:
        messagebox.showinfo("Undo", "Nothing to undo.")
        return

    sid = _last_deleted["student"]["id"]
    name = _last_deleted["student"]["name"]
    groups = _last_deleted.get("groups", [])
    payments = _last_deleted.get("payments", [])

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        # Safety check: make sure ID not in use
        c.execute("SELECT 1 FROM students WHERE id = ?", (sid,))
        if c.fetchone():
            messagebox.showerror("Undo Failed", f"ID {sid} already exists. Can't restore.")
            return

        # Insert student (students table now only has id, name)
        c.execute("INSERT INTO students (id, name) VALUES (?, ?)", (sid, name))

        # Restore groups
        for g in groups:
            c.execute("INSERT OR IGNORE INTO groups (name) VALUES (?)", (g,))
            c.execute("SELECT id FROM groups WHERE name = ?", (g,))
            gid = c.fetchone()[0]
            c.execute("INSERT OR IGNORE INTO student_group (student_id, group_id) VALUES (?, ?)", (sid, gid))

        # Restore payments if available
        for p in payments:
            c.execute("""
                INSERT INTO payments (student_id, year, month, paid, payment_date)
                VALUES (?, ?, ?, ?, ?)
            """, (sid, p["year"], p["month"], p["paid"], p["payment_date"]))

        conn.commit()
        refresh_treeview_all()
        messagebox.showinfo("Undo", f"Student {name} (ID {sid}) restored.")
        _last_deleted = None

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Undo Error", str(e))
    finally:
        conn.close()


def open_delete_confirm(student_id):
    """Open a modal that shows student info and asks for confirmation."""
    data = fetch_student(student_id)
    if not data:
        messagebox.showerror("Not found", f"Student ID {student_id} not found.")
        return

    top = ctk.CTkToplevel(ElNajahSchool)
    top.title("Confirm Delete")
    top.geometry("350x230")
    top.lift(); top.focus_force(); top.grab_set()

    # Info
    ctk.CTkLabel(top, text="Confirm delete", font=("Arial", 20)).pack(pady=(12,6))
    info = f"ID: {data['id']}\nName: {data['name']}\nPay: {data['pay']}\nGroups: {', '.join(data['groups']) if data['groups'] else '—'}"
    ctk.CTkLabel(top, text=info, font=("Arial", 20), justify="left").pack(padx=20, pady=8, anchor="w")

    # Buttons
    btn_frame = ctk.CTkFrame(top, fg_color="transparent")
    btn_frame.pack(pady=12, padx=20, fill="x")

    def confirm_and_close():
        ok = perform_delete(student_id)
        top.destroy()
        if ok:
            # offer immediate undo as a yes/no dialog
            if messagebox.askyesno("Deleted", "Student deleted. Undo?"):
                undo_delete()

    ctk.CTkButton(btn_frame, text="Delete", fg_color="#FF0000", command=confirm_and_close).pack(side="left", padx=10)
    ctk.CTkButton(btn_frame, text="Cancel", command=top.destroy).pack(side="left", padx=10)

def start_delete_selected():
    sel = tree.focus()
    if not sel:
        messagebox.showwarning("Selection", "Select a student to delete.")
        return
    try:
        student_id = int(tree.item(sel, "values")[0])
    except Exception:
        messagebox.showerror("Error", "Invalid selection.")
        return
    open_delete_confirm(student_id)

# wire the button (place after button3 is created)


button3 = ctk.CTkButton(frame, text="Delete", font=("Arial", 16), fg_color="#F13D3D", text_color=text)
button3.configure(command=start_delete_selected)
button3.pack(side="left", padx=(5, 0))


# === Treeview Table (ttk is kept) ===
columns = ("id", "name", "group", "monthly payment")
tree = ttk.Treeview(ElNajahSchool, columns=columns, show="headings")

tree.heading("id", text="ID")
tree.heading("name", text="Name")
tree.heading("group", text="Groups")
tree.heading("monthly payment", text="Monthly Payment")

tree.column("id", anchor="center", width=80)
tree.column("name", anchor="center", width=280)
tree.column("group", anchor="center", width=220)
tree.column("monthly payment", anchor="center", width=75)
tree.pack(fill="both", expand=True)

tree.tag_configure("evenrow", background="#f5faff")
tree.tag_configure("oddrow", background="white")

# === Style Configuration for Treeview ===
style = ttk.Style()
style.theme_use("default")
style.configure("Treeview", rowheight=30, font=("Arial", 12))
style.configure("Treeview.Heading", font=("Arial", 12, "bold"))

def setup_tree_columns(tree):
    tree["columns"] = ("id", "name", "group", "monthly_payment")
    tree["show"] = "headings"

    tree.heading("id", text="ID")
    tree.heading("name", text="Name")
    tree.heading("group", text="Group")
    tree.heading("monthly_payment", text="Monthly Payment")

    tree.column("id", width=60, anchor="center")
    tree.column("name", width=180, anchor="w")
    tree.column("group", width=120, anchor="w")
    tree.column("monthly_payment", width=120, anchor="center")


# === Header Click Event ===
# Helper: run query and update tree
def _update_tree_from_query(sql, params=()):
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    tree.delete(*tree.get_children())  # clear old data

    for i, row in enumerate(rows):
        student_id, name, groups, payment_status = row

        # Build tag list
        tags = []
        if payment_status:  
            tags.append(payment_status.lower())  # paid/unpaid/no record
        tags.append("evenrow" if i % 2 == 0 else "oddrow")  # alternating rows

        tree.insert("", "end", values=row, tags=tags)

    # Payment colors
    tree.tag_configure("paid", foreground="green")
    tree.tag_configure("unpaid", foreground="red")
    tree.tag_configure("no record", foreground="orange")

    # Row striping
    tree.tag_configure("evenrow", background="#f2f2f2")  # light gray
    tree.tag_configure("oddrow", background="#ffffff")   # white





# 1) ID: show all students, sorted by id

def show_sorted_by_id():
    for i in tree.get_children():
        tree.delete(i)
    setup_tree_columns(tree)

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT 
            s.id,
            s.name,
            COALESCE(GROUP_CONCAT(DISTINCT g.name), '—') AS groups,
            MAX(CASE WHEN p.paid = 'paid' THEN 'Paid' ELSE 'Unpaid' END) AS payment_status
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        LEFT JOIN payments p ON s.id = p.student_id
        GROUP BY s.id, s.name
        ORDER BY s.id ASC
    """)
    for row in c.fetchall():
        tree.insert("", "end", values=row)
    conn.close()




# 2) Name: show all students, sorted alphabetically
# --- ensure the tree shows ID-sorted view on startup ---
def set_tree_default_view():
    show_sorted_by_id()
    children = tree.get_children()
    if children:
        first = children[0]
        tree.selection_set(first)
        tree.focus(first)
        tree.see(first)
        tree.selection_remove(tree.selection())

# call it once at startup (after tree exists and DB is initialized)
set_tree_default_view()

def show_sorted_by_name():
    for i in tree.get_children():
        tree.delete(i)
    setup_tree_columns(tree)

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT 
            s.id,
            s.name,
            COALESCE(GROUP_CONCAT(DISTINCT g.name), '—') AS groups,
            MAX(CASE WHEN p.paid = 'paid' THEN 'Paid' ELSE 'Unpaid' END) AS payment_status
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        LEFT JOIN payments p ON s.id = p.student_id
        GROUP BY s.id, s.name
        ORDER BY s.name COLLATE NOCASE ASC
    """)
    for row in c.fetchall():
        tree.insert("", "end", values=row)
    conn.close()



# 3) Pay: show students who did NOT pay
def open_month_selector_and_show():
    now = datetime.now()
    current_year = now.year
    current_month_index = now.month - 1  # 0-based index for the months list

    years = [str(y) for y in range(current_year - 5, current_year + 6)]  # 5 years back and forward
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]

    top = ctk.CTkToplevel(ElNajahSchool)
    top.title("Select Month")
    top.geometry("360x220")
    top.grab_set()
    top.focus_force()

    ctk.CTkLabel(top, text="Select Year and Month:", font=("Arial", 14)).pack(pady=(12,6))

    # Year dropdown
    year_var = ctk.StringVar(value=str(current_year))  # default to current year
    ctk.CTkLabel(top, text="Year:", font=("Arial", 12)).pack(anchor='w', padx=12)
    ctk.CTkOptionMenu(top, values=years, variable=year_var).pack(pady=6, padx=12, fill='x')

    # Month dropdown
    month_var = ctk.StringVar(value=months[current_month_index])  # default to current month
    ctk.CTkLabel(top, text="Month:", font=("Arial", 12)).pack(anchor='w', padx=12)
    ctk.CTkOptionMenu(top, values=months, variable=month_var).pack(pady=6, padx=12, fill='x')

    # Buttons
    btn_frame = ctk.CTkFrame(top, fg_color="transparent")
    btn_frame.pack(pady=8, padx=12, fill='x')

    def apply_and_close():
        show_unpaid_for_month(year_var.get(), month_var.get())
        top.destroy()

    ctk.CTkButton(btn_frame, text="Show", command=apply_and_close).pack(side='left', padx=6)
    ctk.CTkButton(btn_frame, text="Cancel", command=top.destroy).pack(side='left', padx=6)


def show_unpaid_for_month(year, month_name):
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    month_number = months.index(month_name) + 1

    # Build a YYYY-MM-DD for the selected period (always day=1)
    selected_date = f"{int(year)}-{month_number:02d}-01"
    for i in tree.get_children():
        tree.delete(i)
    setup_tree_columns(tree)


    sql = """
        SELECT s.id, s.name,
               COALESCE(GROUP_CONCAT(g.name), '—') AS groups,
               CASE
                   -- Compare only year and month, not the day
                   WHEN strftime('%Y-%m', ?) < strftime('%Y-%m', s.join_date) THEN 'No record'
                   WHEN p.paid = 'paid' THEN 'Paid'
                   WHEN p.paid = 'unpaid' THEN 'Unpaid'
                   ELSE 'Unpaid'
               END AS monthly_payment
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        LEFT JOIN payments p 
               ON s.id = p.student_id AND p.year = ? AND p.month = ?
        GROUP BY s.id
        ORDER BY 
            CASE 
                WHEN monthly_payment = 'Unpaid' THEN 0
                WHEN monthly_payment = 'No record' THEN 1
                ELSE 2
            END,
            s.id
    """
    _update_tree_from_query(sql, (selected_date, int(year), month_number))





# 4) Group selector modal + show by group
def show_by_group(group_name):

    now = datetime.now()
    current_year = now.year
    current_month = now.month  # 1-12
    for i in tree.get_children():
        tree.delete(i)
    setup_tree_columns(tree)


    sql = """
        SELECT s.id, s.name,
               COALESCE(GROUP_CONCAT(DISTINCT g2.name), '—') AS groups,
               COALESCE(p.paid, 'No record') AS monthly_payment
        FROM students s
        JOIN student_group sg ON s.id = sg.student_id
        JOIN groups g ON sg.group_id = g.id
        LEFT JOIN student_group sg2 ON s.id = sg2.student_id
        LEFT JOIN groups g2 ON sg2.group_id = g2.id
        LEFT JOIN payments p
               ON s.id = p.student_id AND p.year = ? AND p.month = ?
        WHERE g.name = ?
        GROUP BY s.id
        ORDER BY s.name COLLATE NOCASE
    """
    _update_tree_from_query(sql, (current_year, current_month, group_name))




def open_group_selector_and_show():
    groups = get_all_groups()
    if not groups:
        messagebox.showinfo("No groups", "There are no groups in the database.")
        return

    top = ctk.CTkToplevel(ElNajahSchool)
    top.title("Choose Group")
    top.geometry("360x140")
    top.grab_set(); top.focus_force()

    ctk.CTkLabel(top, text="Select a group to display:", font=("Arial", 14)).pack(pady=(12,6))

    # Option menu is simple and works well
    selected = ctk.StringVar(value=groups[0])
    option = ctk.CTkOptionMenu(top, values=groups, variable=selected)
    option.pack(pady=6, padx=12, fill='x')

    def apply_and_close():
        show_by_group(selected.get())
        top.destroy()

    btn_frame = ctk.CTkFrame(top, fg_color="transparent")
    btn_frame.pack(pady=8, padx=12, fill='x')
    ctk.CTkButton(btn_frame, text="Show", command=apply_and_close).pack(side='left', padx=6)
    ctk.CTkButton(btn_frame, text="Cancel", command=top.destroy).pack(side='left', padx=6)


def on_treeview_heading_click(event):
    region = tree.identify_region(event.x, event.y)
    if region != "heading":
        return

    col = tree.identify_column(event.x)
    col_map = {
        '#1': 'id',
        '#2': 'name',
        '#3': 'group',
        '#4': 'monthly_payment'
    }
    col_name = col_map.get(col)
    if not col_name:
        return

    if col_name == "id":
        show_sorted_by_id()
    elif col_name == "name":
        show_sorted_by_name()
    elif col_name == "monthly_payment":
        open_month_selector_and_show()
    elif col_name == "group":
        open_group_selector_and_show()

# bind once (replace your previous binding)
tree.bind("<Button-1>", on_treeview_heading_click)



# === Payments History Logs Button ===
history_button = ctk.CTkButton(
    ElNajahSchool,
    text="Payments History Logs",
    font=("Arial", 30),
    text_color=text,         # defined earlier in your theme
    fg_color=primary,        # button background
    hover_color=hover,       # darker on hover
    border_width=3,          # border thickness
    border_color="gray",     # border color
    command=paymants_log.open_full_window
)
history_button.place(
    relx=0.5, rely=0.95, anchor="s", relwidth=1.0
)

# === Copyright Label ===
def copy_email_to_clipboard():
    ElNajahSchool.clipboard_clear()
    ElNajahSchool.clipboard_append("ywkuoamb@gmail.com")
    ElNajahSchool.update()
    messagebox.showinfo("Copied", "Email address copied to clipboard.")


copyright_button = ctk.CTkButton(
    ElNajahSchool,
    text="© 2025/2026 El Najah School. All rights reserved. Made by Rare Technology: ywkuoamb@gmail.com",
    font=("Arial", 15),
    text_color=text,
    fg_color=secondary,
    hover_color=hover,
    command=copy_email_to_clipboard
)
copyright_button.place(relx=0.5, rely=1, anchor="s")

# === Start App ===
ElNajahSchool.mainloop()