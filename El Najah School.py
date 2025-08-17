import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import shutil
import datetime
from datetime import datetime
import os
import time
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image
from openpyxl import Workbook
from tkinter import filedialog
import webbrowser
import urllib.parse
from PIL import Image, ImageTk

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# === Database ===
def init_db():
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()

    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pay TEXT CHECK(pay IN ('paid', 'unpaid')) NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS student_group (
            student_id INTEGER,
            group_id INTEGER,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(group_id) REFERENCES groups(id),
            PRIMARY KEY (student_id, group_id)
        )
    ''')

    conn.commit()
    conn.close()
init_db()  # Once per app launch

def refresh_db_view():
    """Reload all students from DB and refresh Treeview display."""
    # Clear existing rows
    tree.delete(*tree.get_children())

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        c.execute("""
            SELECT s.id, s.name, GROUP_CONCAT(g.name), s.pay
            FROM students s
            LEFT JOIN student_group sg ON s.id = sg.student_id
            LEFT JOIN groups g ON sg.group_id = g.id
            GROUP BY s.id
            ORDER BY s.id
        """)
        rows = c.fetchall()
    finally:
        conn.close()

    # Reinsert rows into Treeview
    for i, row in enumerate(rows):
        tree.insert(
            "",
            "end",
            values=(row[0], row[1], row[2] or "", row[3]),
            tags=("evenrow" if i % 2 == 0 else "oddrow",)
        )

    # Optional: clear selection after refresh
    tree.selection_remove(tree.selection())

def backup_database():
    # Create a timestamp for unique backup names
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"elnajah_backup_{timestamp}.db"

    # Backup directory
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)

    # Copy the DB file
    shutil.copyfile("elnajah.db", os.path.join(backup_dir, backup_name))

def reset_pay_status():
    # Confirm with user
    if not messagebox.askyesno(
        "Confirm Monthly Reset",
        "Are you sure you want to mark ALL students as unpaid?\n"
        "This will overwrite current payment statuses.\n\n"
        "A backup will be created first."
    ):
        return

    # Backup before reset
    try:
        backup_database()
    except Exception as e:
        messagebox.showerror("Backup Failed", f"Could not create backup.\nError: {e}")
        return

    # Reset payments
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        c.execute("UPDATE students SET pay = 'unpaid'")
        conn.commit()
    finally:
        conn.close()

    refresh_treeview_all()
    messagebox.showinfo("Monthly Reset", "All students have been marked as unpaid.\nBackup was saved.")

def export_group_to_pdf(group_name):
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT s.id, s.name, s.pay
        FROM students s
        JOIN student_group sg ON s.id = sg.student_id
        JOIN groups g ON sg.group_id = g.id
        WHERE g.name = ?
        ORDER BY s.name
    """, (group_name,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        messagebox.showinfo("No Data", f"No students found in group '{group_name}'.")
        return

    # Create PDF file name
    os.makedirs("exports", exist_ok=True)
    filename = os.path.join("exports",f"group_{group_name.replace(' ', '_')}.pdf")

    # Create PDF
    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # Title
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawString(50, height - 50, f"El Najah School")
    
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, height - 80, f"Group: {group_name}")

    # Table header
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, height - 120, "ID")
    pdf.drawString(150, height - 120, "Name")
    pdf.drawString(400, height - 120, "Pay Status")

    # Table rows
    y = height - 160
    pdf.setFont("Helvetica", 12)
    for sid, name, pay in rows:
        pdf.drawString(50, y, str(sid))
        pdf.drawString(150, y, name)
        pdf.drawString(400, y, pay or "")
        y -= 20
        if y < 50:  # New page
            pdf.showPage()
            y = height - 50

    pdf.save()
    messagebox.showinfo("Export Complete", f"PDF saved: {filename}")

def open_group_selector_and_export():
    groups = get_all_groups()
    if not groups:
        messagebox.showinfo("No groups", "There are no groups in the database.")
        return

    top = ctk.CTkToplevel(ElNajahSchool)
    top.title("Export Group to PDF")
    top.geometry("360x140")
    top.grab_set(); top.focus_force()

    ctk.CTkLabel(top, text="Select a group to export:", font=("Arial", 14)).pack(pady=(12,6))

    selected = ctk.StringVar(value=groups[0])
    option = ctk.CTkOptionMenu(top, values=groups, variable=selected)
    option.pack(pady=6, padx=12, fill='x')

    def export_and_close():
        export_group_to_pdf(selected.get())
        top.destroy()

    btn_frame = ctk.CTkFrame(top, fg_color="transparent")
    btn_frame.pack(pady=8, padx=12, fill='x')
    ctk.CTkButton(btn_frame, text="Export PDF", command=export_and_close).pack(side='left', padx=6)
    ctk.CTkButton(btn_frame, text="Cancel", command=top.destroy).pack(side='left', padx=6)

def delete_groupless_students():
    if not messagebox.askyesno(
        "Confirm Delete",
        "Are you sure you want to delete ALL students who have no groups?\n"
        "This cannot be undone (unless you restore from a backup)."
    ):
        return

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        # Find groupless students
        c.execute("""
            SELECT id, name
            FROM students
            WHERE id NOT IN (SELECT student_id FROM student_group)
        """)
        groupless = c.fetchall()

        if not groupless:
            messagebox.showinfo("No Action", "No groupless students found.")
            return

        # Delete them
        c.execute("""
            DELETE FROM students
            WHERE id NOT IN (SELECT student_id FROM student_group)
        """)
        conn.commit()

        refresh_treeview_all()

        deleted_names = ", ".join([name for _, name in groupless])
        messagebox.showinfo("Deleted", f"Groupless students deleted:\n{deleted_names}")

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Error", str(e))
    finally:
        conn.close()

    refresh_treeview_all()

def export_all_students_excel():
    # Fetch all students with their groups
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT s.id, s.name, GROUP_CONCAT(g.name), s.pay
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        GROUP BY s.id
        ORDER BY s.id
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        messagebox.showinfo("No Data", "No students found to export.")
        return

    # Prepare filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    export_dir = "exports"
    os.makedirs("exports", exist_ok=True)
    filename = os.path.join("exports", "all_students_" + timestamp + ".xlsx")

    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"

    # Header row
    ws.append(["ID", "Name", "Groups", "Pay Status"])

    # Data rows
    for row in rows:
        ws.append(row)

    # Save file
    wb.save(filename)
    messagebox.showinfo("Export Complete", f"Excel file saved:\n{filename}")

def restore_backup():
    # Ask the user to choose a backup file
    backup_path = filedialog.askopenfilename(
        title="Select Backup File",
        initialdir="backups",
        filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
    )

    if not backup_path:
        return  # User canceled

    # Confirm restore
    if not messagebox.askyesno(
        "Confirm Restore",
        f"Restore the database from:\n{backup_path}?\n\n"
        "This will overwrite the current database and cannot be undone."
    ):
        return

    try:
        # Make a backup of the current DB before overwriting
        backup_database()

        # Replace current DB with selected backup
        shutil.copyfile(backup_path, "elnajah.db")

        refresh_treeview_all()
        messagebox.showinfo("Restore Complete", f"Database restored from:\n{backup_path}")

    except Exception as e:
        messagebox.showerror("Restore Failed", str(e))

def purge_old_backups(days=30):
    if not os.path.exists("backups"):
        messagebox.showinfo("No Backups", "Backup folder does not exist.")
        return

    # Confirm purge
    if not messagebox.askyesno(
        "Confirm Purge",
        f"Delete all backups older than {days} days?\nThis cannot be undone."
    ):
        return

    now = time.time()
    deleted_files = []

    for filename in os.listdir("backups"):
        filepath = os.path.join("backups", filename)
        if os.path.isfile(filepath):
            file_age_days = (now - os.path.getmtime(filepath)) / (60 * 60 * 24)
            if file_age_days > days:
                try:
                    os.remove(filepath)
                    deleted_files.append(filename)
                except Exception as e:
                    messagebox.showerror("Error Deleting", f"{filename}: {e}")

    if deleted_files:
        messagebox.showinfo("Purge Complete", f"Deleted backups:\n" + "\n".join(deleted_files))
    else:
        messagebox.showinfo("Purge Complete", "No old backups were deleted.")

def contact_support():
    # Replace with your email
    your_email = "ywkouamb@gmail.com"
    subject = "El Najah School Support"
    body = "سلام الله عليكم ورحمة الله وبركاته\n\n"

    # Encode for URL
    
    subject_encoded = urllib.parse.quote(subject)
    body_encoded = urllib.parse.quote(body)

    # Email link
    #email_url = f"mailto:{your_email}?subject={subject_encoded}&body={body_encoded}"
    #webbrowser.open(email_url)

    # Gmail compose link
    gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={your_email}&su={subject_encoded}&body={body_encoded}"
    webbrowser.open(gmail_url)

def merge_duplicate_students():
    # Step 1: Find duplicate student names
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT name, COUNT(*) as cnt
        FROM students
        GROUP BY name
        HAVING cnt > 1
    """)
    duplicates = c.fetchall()
    conn.close()

    if not duplicates:
        messagebox.showinfo("Merge Duplicates", "No duplicate student names found.")
        return

    def show_duplicate_modal(index=0):
        # Stop if no more duplicates
        if index >= len(duplicates):
            refresh_treeview_all()
            return

        name = duplicates[index][0]

        # Step 2: Get all students with this name
        conn2 = sqlite3.connect("elnajah.db")
        c2 = conn2.cursor()
        c2.execute("""
            SELECT s.id, s.name, s.pay, GROUP_CONCAT(g.name)
            FROM students s
            LEFT JOIN student_group sg ON s.id = sg.student_id
            LEFT JOIN groups g ON sg.group_id = g.id
            WHERE s.name = ?
            GROUP BY s.id
            ORDER BY s.id
        """, (name,))
        students_with_same_name = c2.fetchall()
        conn2.close()

        # Step 3: Modal window
        top = ctk.CTkToplevel(ElNajahSchool)
        top.title(f"Merge Duplicates — {name}")
        top.geometry("500x400")
        top.grab_set()
        top.focus_force()

        ctk.CTkLabel(top, text=f"Select student to KEEP for name: {name}", font=("Arial", 16)).pack(pady=8)

        keep_var = ctk.IntVar(value=students_with_same_name[0][0])

        # Show each duplicate with details
        for sid, nm, pay, groups in students_with_same_name:
            info = f"ID: {sid} | Pay: {pay} | Groups: {groups or '—'}"
            ctk.CTkRadioButton(top, text=info, variable=keep_var, value=sid).pack(anchor="w", padx=10, pady=4)

        def confirm_merge():
            main_id = keep_var.get()
            extra_ids = [sid for sid, _, _, _ in students_with_same_name if sid != main_id]

            if extra_ids:
                conn3 = sqlite3.connect("elnajah.db")
                c3 = conn3.cursor()

                # Check if any duplicate has pay = 'paid'
                c3.execute(
                    f"SELECT pay FROM students WHERE id IN ({','.join('?' * (len(extra_ids) + 1))})",
                    [main_id] + extra_ids
                )
                pay_statuses = [row[0] for row in c3.fetchall()]
                if "paid" in [status.lower() for status in pay_statuses if status]:
                    c3.execute("UPDATE students SET pay = 'paid' WHERE id = ?", (main_id,))

                # Move groups without duplicates
                for dup_id in extra_ids:
                    c3.execute("""
                        INSERT OR IGNORE INTO student_group (student_id, group_id)
                        SELECT ?, group_id FROM student_group WHERE student_id = ?
                    """, (main_id, dup_id))

                # Delete duplicates
                c3.execute(f"DELETE FROM students WHERE id IN ({','.join('?' * len(extra_ids))})", extra_ids)

                c3.execute("""
                    DELETE FROM student_group
                    WHERE student_id NOT IN (SELECT id FROM students)
                """)

                conn3.commit()
                conn3.close()

                messagebox.showinfo("Merged", f"Merged {len(extra_ids)} into ID {main_id}.")

            top.destroy()
            show_duplicate_modal(index + 1)

        def skip_merge():
            top.destroy()
            show_duplicate_modal(index + 1)

        # Step 4: Buttons
        ctk.CTkButton(top, text="Merge", command=confirm_merge).pack(pady=8)
        ctk.CTkButton(top, text="Skip", command=skip_merge).pack()

    # Step 5: Start with first duplicate set
    show_duplicate_modal()


def bulk_remove_group_if_only_group():
    groups = get_all_groups()
    if not groups:
        messagebox.showinfo("No Groups", "There are no groups in the database.")
        return

    # Ask user to choose group
    top = ctk.CTkToplevel(ElNajahSchool)
    top.title("Bulk Remove Group")
    top.geometry("360x140")
    top.grab_set(); top.focus_force()

    ctk.CTkLabel(top, text="Select a group to remove (only if sole group):", font=("Arial", 14)).pack(pady=(12,6))

    selected_group = ctk.StringVar(value=groups[0])
    option = ctk.CTkOptionMenu(top, values=groups, variable=selected_group)
    option.pack(pady=6, padx=12, fill='x')

    def confirm_bulk_remove():
        group_name = selected_group.get()
        if not messagebox.askyesno("Confirm", f"Remove group '{group_name}' ONLY from students who are in no other groups?"):
            return

        conn = sqlite3.connect("elnajah.db")
        c = conn.cursor()

        try:
            # Get ID of the chosen group
            c.execute("SELECT id FROM groups WHERE name = ?", (group_name,))
            row = c.fetchone()
            if not row:
                messagebox.showerror("Error", "Group not found.")
                conn.close()
                return
            group_id = row[0]

            # Find students who are ONLY in this group
            c.execute("""
                SELECT s.id
                FROM students s
                JOIN student_group sg ON s.id = sg.student_id
                WHERE sg.group_id = ?
                GROUP BY s.id
                HAVING COUNT(sg.group_id) = 1
            """, (group_id,))
            students_to_remove = [r[0] for r in c.fetchall()]

            if not students_to_remove:
                messagebox.showinfo("No Action", f"No students found who are ONLY in '{group_name}'.")
                conn.close()
                return

            # Delete links for those students
            c.executemany("DELETE FROM student_group WHERE student_id = ? AND group_id = ?", 
                          [(sid, group_id) for sid in students_to_remove])
            conn.commit()

            refresh_treeview_all()
            messagebox.showinfo("Bulk Remove Complete", 
                                f"Removed group '{group_name}' from {len(students_to_remove)} student(s).")
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()

        top.destroy()

    btn_frame = ctk.CTkFrame(top, fg_color="transparent")
    btn_frame.pack(pady=8, padx=12, fill='x')
    ctk.CTkButton(btn_frame, text="Remove", command=confirm_bulk_remove).pack(side='left', padx=6)
    ctk.CTkButton(btn_frame, text="Cancel", command=top.destroy).pack(side='left', padx=6)

def export_unpaid_students_pdf():
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT g.name AS group_name, s.name AS student_name
        FROM students s
        JOIN student_group sg ON s.id = sg.student_id
        JOIN groups g ON sg.group_id = g.id
        WHERE LOWER(s.pay) != 'paid' OR s.pay IS NULL
        ORDER BY g.name, s.name
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        messagebox.showinfo("No Unpaid", "No unpaid students found.")
        return

    # Prepare filename
    os.makedirs("exports", exist_ok=True)
    filename = os.path.join("exports", "unpaid_students.pdf")

    # Create PDF
    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, height - 50, "Unpaid Students Report")

    y = height - 80
    current_group = None

    pdf.setFont("Helvetica", 12)
    for group_name, student_name in rows:
        if group_name != current_group:
            current_group = group_name
            y -= 20
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(50, y, f"Group: {group_name}")
            y -= 15
            pdf.setFont("Helvetica", 12)

        pdf.drawString(70, y, f"- {student_name}")
        y -= 15

        # New page if needed
        if y < 50:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 12)

    pdf.save()
    messagebox.showinfo("Export Complete", f"PDF saved to:\n{filename}")


def export_student_count_pdf():
    # Ensure export folder exists
    export_folder = "exports"
    os.makedirs(export_folder, exist_ok=True)

    # Connect to DB
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()

    # Get total students
    c.execute("SELECT COUNT(*) FROM students")
    total_students = c.fetchone()[0]

    # Get group counts
    c.execute("""
        SELECT g.name, COUNT(sg.student_id) as count
        FROM groups g
        LEFT JOIN student_group sg ON g.id = sg.group_id
        GROUP BY g.id
        ORDER BY g.name
    """)
    group_counts = c.fetchall()

    conn.close()

    # Prepare PDF file path
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    pdf_path = os.path.join(export_folder, f"student_count.pdf")

    # Create PDF
    c_pdf = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    # Title
    c_pdf.setFont("Helvetica-Bold", 18)
    c_pdf.drawString(50, height - 50, "ElNajahSchool - Student Count Report")

    # Date
    c_pdf.setFont("Helvetica", 10)
    c_pdf.drawString(50, height - 70, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Total students
    c_pdf.setFont("Helvetica-Bold", 14)
    c_pdf.drawString(50, height - 110, f"Total Students: {total_students}")

    # Group counts
    c_pdf.setFont("Helvetica-Bold", 12)
    c_pdf.drawString(50, height - 150, "Students by Group:")

    y_pos = height - 170
    c_pdf.setFont("Helvetica", 12)
    for group_name, count in group_counts:
        c_pdf.drawString(70, y_pos, f"- {group_name}: {count}")
        y_pos -= 20

    # If there are groups with no students
    if not group_counts:
        c_pdf.drawString(70, y_pos, "No groups found.")

    c_pdf.showPage()
    c_pdf.save()

    messagebox.showinfo("Export Complete", f"Student count report saved to:\n{pdf_path}")


# === Color Scheme ===
background = "#F4F7FA"
primary    = "#3B82F6"  # Blue-500
secondary  = "#60A5FA"  # Blue-400
text       = "#1F2937"  # Gray-800

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
file_menu.add_command(label="Refresh", command=refresh_db_view)
file_menu.add_command(label="Exit", command=ElNajahSchool.quit)
menubar.add_cascade(label="Menu", menu=file_menu)
ElNajahSchool.config(menu=menubar)

# === Tool Bar (still standard Tk) ===
tools_menu = Menu(menubar, tearoff=0)
tools_menu.add_command(label="Reset Payment", command=reset_pay_status)
tools_menu.add_command(label="Delete Groupless Students", command=delete_groupless_students)
tools_menu.add_command(label="Merge Duplicate Students", command=merge_duplicate_students)
tools_menu.add_command(label="Bulk Remove Group if Only Group", command=bulk_remove_group_if_only_group)
menubar.add_cascade(label="Tools", menu=tools_menu)

# === backup Bar (still standard Tk) ===
backup_menu = Menu(menubar, tearoff=0)
backup_menu.add_command(label="Backup Database", command=backup_database)
backup_menu.add_command(label="Restore Database", command=restore_backup)
backup_menu.add_command(label="Purge Old Backups", command=purge_old_backups)
menubar.add_cascade(label="Backup", menu=backup_menu)

# === Exports Menu (still standard Tk) ===
Export_menu = Menu(menubar, tearoff=0)
Export_menu.add_command(label="Export Group to PDF", command=open_group_selector_and_export)
Export_menu.add_command(label="Export All Students to Excel", command=export_all_students_excel)
Export_menu.add_command(label="Export Unpaid Students to PDF", command=export_unpaid_students_pdf)
Export_menu.add_command(label="Export Student Count to PDF", command=export_student_count_pdf)
menubar.add_cascade(label="Export", menu=Export_menu)

# === Help Menu (still standard Tk) ===
help_menu = Menu(menubar, tearoff=0)
help_menu.add_command(label="Contact Support", command=contact_support)
menubar.add_cascade(label="Help", menu=help_menu)

# === Welcome Label ===
logo_img = ctk.CTkImage(light_image=Image.open("El Najah School logo.png"),
                        dark_image=Image.open("El Najah School logo.png"),
                        size=(679/1.8 , 247/1.8))

# Display image in a label
label = ctk.CTkLabel(ElNajahSchool, image=logo_img, text="")  # text="" to hide label text
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
    top.geometry("500x600")
    top.lift()
    top.focus_force()
    top.grab_set()

    ctk.CTkLabel(top, text="Add new student", font=("Arial", 24)).pack(pady=20)

    # === ID Field ===
    id_frame = ctk.CTkFrame(top, fg_color="transparent")
    id_frame.pack(pady=10, padx=20, fill='x')

    ctk.CTkLabel(id_frame, text="ID:", font=("Arial", 18)).pack(side='left', padx=(0, 10))
    id_entry = ctk.CTkEntry(id_frame, font=("Arial", 18), justify='right')
    id_entry.pack(side='left', fill='x', expand=True)


    # === Name Field ===
    name_frame = ctk.CTkFrame(top, fg_color="transparent")
    name_frame.pack(pady=10, padx=20, fill='x')

    ctk.CTkLabel(name_frame, text="Name:", font=("Arial", 18)).pack(side='left', padx=(0, 10))

    entry = ctk.CTkEntry(name_frame, font=("Arial", 18), justify='right')
    entry.pack(side='left', fill='x', expand=True)

    # === Pay Status ===
    pay_frame = ctk.CTkFrame(top, fg_color="transparent")
    pay_frame.pack(pady=10, padx=20, fill='x')

    ctk.CTkLabel(pay_frame, text="Pay:", font=("Arial", 18), width=80, anchor='e').pack(side='left')

    radio_frame = ctk.CTkFrame(pay_frame, fg_color="transparent")
    radio_frame.pack(side='left', expand=True)

    radio_var = ctk.StringVar(value="paid")
    ctk.CTkRadioButton(radio_frame, text="Paid", variable=radio_var, value="paid").pack(side='left', padx=10)
    ctk.CTkRadioButton(radio_frame, text="Unpaid", variable=radio_var, value="unpaid").pack(side='left', padx=10)

    # === Group Selection ===
    group_selection_frame = ctk.CTkFrame(top, fg_color="transparent")
    group_selection_frame.pack(pady=10, padx=20, fill='both', expand=True)

    ctk.CTkLabel(group_selection_frame, text="Select Groups:", font=("Arial", 18)).pack(anchor='w', pady=5)

    scrollable = ctk.CTkScrollableFrame(group_selection_frame, width=400, height=150, fg_color="white")
    scrollable.pack(fill='both', expand=False)

    group_vars = {}

    def reload_groups():
        for widget in scrollable.winfo_children():
            widget.destroy()

        group_names = get_all_groups()  # Fetch from DB
        for name in group_names:
            var = ctk.BooleanVar(value=False)
            checkbox = ctk.CTkCheckBox(scrollable, text=name, variable=var)
            checkbox.pack(anchor="w", pady=2, padx=10)
            group_vars[name] = var

    reload_groups()


    # === Add & Cancel Buttons ===
    button1_frame = ctk.CTkFrame(top, fg_color="transparent")
    button1_frame.pack(pady=10, padx=20, fill='x')
    button2_frame = ctk.CTkFrame(top, fg_color="transparent")
    button2_frame.pack(pady=10, padx=20, fill='x')

    def handle_add_student():
        name = entry.get()
        pay_status = radio_var.get()
        selected_groups = [g for g, v in group_vars.items() if v.get()]
    
        id_text = id_entry.get().strip()
        if not id_text:
            messagebox.showerror("Invalid ID", "Student ID is required.")
            return
        if not id_text.isdigit():
            messagebox.showerror("Invalid ID", "ID must be a number.")
            return

        manual_id = int(id_text)

        add_student(name, pay_status, selected_groups, manual_id)
        top.destroy()


    ctk.CTkButton(button1_frame, text="Add Student", command=handle_add_student).pack(padx=10)
    ctk.CTkButton(button2_frame, text="Cancel", command=top.destroy).pack(padx=10)

def get_all_groups():
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("SELECT name FROM groups ORDER BY name")
    groups = [row[0] for row in c.fetchall()]
    conn.close()
    return groups


def add_student(name, pay_status, selected_groups, manual_id):
    if not manual_id:
        messagebox.showerror("Error", "Student ID is required.")
        return
    if not name.strip():
        messagebox.showerror("Error", "Student name is required.")
        return

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()

    try:
        # Check if ID exists
        c.execute("SELECT 1 FROM students WHERE id = ?", (manual_id,))
        if c.fetchone():
            messagebox.showerror("ID Exists", f"Student ID {manual_id} already exists.")
            return

        # Insert with required ID
        c.execute("INSERT INTO students (id, name, pay) VALUES (?, ?, ?)", (manual_id, name, pay_status))

        # Link to groups
        for group_name in selected_groups:
            c.execute("INSERT OR IGNORE INTO groups (name) VALUES (?)", (group_name,))
            c.execute("SELECT id FROM groups WHERE name = ?", (group_name,))
            group_id = c.fetchone()[0]
            c.execute("INSERT INTO student_group (student_id, group_id) VALUES (?, ?)", (manual_id, group_id))

        conn.commit()
        print(f"✅ Student '{name}' added with ID {manual_id}")
        messagebox.showinfo("Success", f"Student '{name}' added.")

    except Exception as e:
        messagebox.showerror("Error", str(e))

    finally:
        conn.close()
    refresh_treeview_all()


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



def search_students():
    search_type = radio_var.get()
    search_text = entry1_var.get().strip()

    if search_type not in ["ID", "Name", "Group"]:
        messagebox.showerror("Error", "Please select a search type.")
        return
    if not search_text:
        messagebox.showerror("Error", "Please enter search text.")
        return

    # Clear Treeview
    for item in tree.get_children():
        tree.delete(item)

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()

    if search_type == "ID":
        c.execute("""
            SELECT s.id, s.name, GROUP_CONCAT(g.name), s.pay
            FROM students s
            LEFT JOIN student_group sg ON s.id = sg.student_id
            LEFT JOIN groups g ON sg.group_id = g.id
            WHERE s.id = ?
            GROUP BY s.id
        """, (search_text,))
    
    elif search_type == "Name":
        c.execute("""
            SELECT s.id, s.name, GROUP_CONCAT(g.name), s.pay
            FROM students s
            LEFT JOIN student_group sg ON s.id = sg.student_id
            LEFT JOIN groups g ON sg.group_id = g.id
            WHERE s.name LIKE ?
            GROUP BY s.id
        """, ('%' + search_text + '%',))
    
    elif search_type == "Group":
        c.execute("""
            SELECT s.id, s.name, GROUP_CONCAT(g.name), s.pay
            FROM students s
            LEFT JOIN student_group sg ON s.id = sg.student_id
            LEFT JOIN groups g ON sg.group_id = g.id
            WHERE g.name LIKE ?
            GROUP BY s.id
        """, ('%' + search_text + '%',))

    rows = c.fetchall()
    conn.close()
        # Insert into Treeview
    for i, row in enumerate(rows):
        tree.insert("", "end", values=row, tags=("evenrow" if i % 2 == 0 else "oddrow",))

button1 = ctk.CTkButton(frame, text="Search", command=search_students, font=("Arial", 16), fg_color=primary, text_color=text)
button1.pack(side="left", padx=(5, 0))

def fetch_student(student_id):
    """Return dict: {'id', 'name', 'pay', 'groups' (list)}"""
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        c.execute("SELECT id, name, pay FROM students WHERE id = ?", (student_id,))
        row = c.fetchone()
        if not row:
            return None
        sid, name, pay = row
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
    Update student's name/pay and reset group links.
    Returns True on success, False on failure (and shows messagebox).
    """
    if not name.strip():
        messagebox.showerror("Validation", "Name is required.")
        return False

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        # Update student row
        c.execute("UPDATE students SET name = ?, pay = ? WHERE id = ?", (name.strip(), pay_status, student_id))

        # Clear existing links
        c.execute("DELETE FROM student_group WHERE student_id = ?", (student_id,))

        # Ensure groups exist and link them
        for group_name in selected_groups:
            c.execute("INSERT OR IGNORE INTO groups (name) VALUES (?)", (group_name,))
            c.execute("SELECT id FROM groups WHERE name = ?", (group_name,))
            gid = c.fetchone()[0]
            c.execute("INSERT INTO student_group (student_id, group_id) VALUES (?, ?)", (student_id, gid))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        messagebox.showerror("DB Error", str(e))
        return False
    finally:
        conn.close()

    refresh_treeview_all()

def refresh_treeview_all():
    # Clears and reloads all students (id, name, groups, pay)
    for item in tree.get_children():
        tree.delete(item)

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        c.execute("""
            SELECT s.id, s.name, GROUP_CONCAT(g.name), s.pay
            FROM students s
            LEFT JOIN student_group sg ON s.id = sg.student_id
            LEFT JOIN groups g ON sg.group_id = g.id
            GROUP BY s.id
            ORDER BY s.id
        """)
        rows = c.fetchall()
    finally:
        conn.close()

    for i, row in enumerate(rows):
        tree.insert("", "end", values=(row[0], row[1], row[2] or "", row[3]),
                    tags=("evenrow" if i % 2 == 0 else "oddrow",))

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
    pay = _last_deleted["student"]["pay"]
    groups = _last_deleted["groups"]

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        # Make sure ID not in use (safety)
        c.execute("SELECT 1 FROM students WHERE id = ?", (sid,))
        if c.fetchone():
            messagebox.showerror("Undo Failed", f"ID {sid} already exists. Can't restore.")
            return

        # insert student
        c.execute("INSERT INTO students (id, name, pay) VALUES (?, ?, ?)", (sid, name, pay))
        # ensure groups exist and re-link
        for g in groups:
            c.execute("INSERT OR IGNORE INTO groups (name) VALUES (?)", (g,))
            c.execute("SELECT id FROM groups WHERE name = ?", (g,))
            gid = c.fetchone()[0]
            c.execute("INSERT OR IGNORE INTO student_group (student_id, group_id) VALUES (?, ?)", (sid, gid))

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
columns = ("id", "name", "group", "pay")
tree = ttk.Treeview(ElNajahSchool, columns=columns, show="headings")

tree.heading("id", text="ID")
tree.heading("name", text="Name")
tree.heading("group", text="Groups")
tree.heading("pay", text="Pay")

tree.column("id", anchor="center", width=80)
tree.column("name", anchor="center", width=280)
tree.column("group", anchor="center", width=220)
tree.column("pay", anchor="center", width=75)
tree.pack(fill="both", expand=True)

tree.tag_configure("evenrow", background="#f5faff")
tree.tag_configure("oddrow", background="white")

# === Style Configuration for Treeview ===
style = ttk.Style()
style.theme_use("default")
style.configure("Treeview", rowheight=30, font=("Arial", 12))
style.configure("Treeview.Heading", font=("Arial", 12, "bold"))

# === Header Click Event ===
# Helper: run query and update tree
def _update_tree_from_query(sql, params=()):
    # clear tree
    for item in tree.get_children():
        tree.delete(item)

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        c.execute(sql, params)
        rows = c.fetchall()
    finally:
        conn.close()

    for i, row in enumerate(rows):
        # make sure row is (id, name, groups, pay)
        tree.insert("", "end", values=(row[0], row[1], row[2] or "", row[3]),
                    tags=("evenrow" if i % 2 == 0 else "oddrow",))

# 1) ID: show all students, sorted by id
def show_sorted_by_id():
    sql = """
        SELECT s.id, s.name, GROUP_CONCAT(g.name), s.pay
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        GROUP BY s.id
        ORDER BY s.id ASC
    """
    _update_tree_from_query(sql)

# 2) Name: show all students, sorted alphabetically
# --- ensure the tree shows ID-sorted view on startup ---
def set_tree_default_view():
    show_sorted_by_id()               # load data sorted by ID
    # optionally select + focus first row for keyboard-friendly UX
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
    sql = """
        SELECT s.id, s.name, GROUP_CONCAT(g.name), s.pay
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        GROUP BY s.id
        ORDER BY s.name COLLATE NOCASE ASC
    """
    _update_tree_from_query(sql)

# 3) Pay: show students who did NOT pay
def show_unpaid():
    sql = """
        SELECT s.id, s.name, GROUP_CONCAT(g.name), s.pay
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        WHERE s.pay IS NULL OR LOWER(s.pay) != 'paid'
        GROUP BY s.id
        ORDER BY s.id
    """
    _update_tree_from_query(sql)

# 4) Group selector modal + show by group
def show_by_group(group_name):
    sql = """
        SELECT s.id, s.name, GROUP_CONCAT(g2.name), s.pay
        FROM students s
        JOIN student_group sg ON s.id = sg.student_id
        JOIN groups g ON sg.group_id = g.id
        LEFT JOIN student_group sg2 ON s.id = sg2.student_id
        LEFT JOIN groups g2 ON sg2.group_id = g2.id
        WHERE g.name = ?
        GROUP BY s.id
        ORDER BY s.name COLLATE NOCASE
    """
    _update_tree_from_query(sql, (group_name,))

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
        '#4': 'pay'
    }
    col_name = col_map.get(col)
    if not col_name:
        return

    # route actions
    if col_name == "id":
        show_sorted_by_id()
    elif col_name == "name":
        show_sorted_by_name()
    elif col_name == "pay":
        show_unpaid()
    elif col_name == "group":
        # open small selector to pick which group to display
        open_group_selector_and_show()

# bind once (replace your previous binding)
tree.bind("<Button-1>", on_treeview_heading_click)

# === Copyright Label ===
def copy_email_to_clipboard():
    ElNajahSchool.clipboard_clear()
    ElNajahSchool.clipboard_append("ywkuoamb@gmail.com")
    ElNajahSchool.update()  # Keeps it in clipboard after program closes
    messagebox.showinfo("Copied", "Email address copied to clipboard.")

# Copyright / Contact Button
contact_button = ctk.CTkButton(
    ElNajahSchool,
    text="© 2025/2026 El Najah School. All rights reserved. made by Rare technology:ywkuoamb@gmail.com",
    font=("Arial", 15),
    text_color="gray",
    fg_color="transparent",
    hover_color="#E5E7EB",
    command=copy_email_to_clipboard
)
contact_button.place(relx=0.5, rely=1, anchor="s")
# === Start App ===
ElNajahSchool.mainloop()
