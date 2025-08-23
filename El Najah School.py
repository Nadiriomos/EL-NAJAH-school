import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import shutil
# Duplicate import commented out (already imported above)
import os
import time
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image
from openpyxl import Workbook
from tkinter import filedialog
import webbrowser
import urllib.parse
from PIL import Image, ImageTk
from tkinter import simpledialog, messagebox

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
now = datetime.now()
# === Database ===
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

init_db()  # Once per app launch
conn = sqlite3.connect("elnajah.db")
cursor = conn.cursor()    

def backup_database():
    # Create a timestamp for unique backup names
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"elnajah_backup_{timestamp}.db"

    # Backup directory
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)

    # Copy the DB file
    shutil.copyfile("elnajah.db", os.path.join(backup_dir, backup_name))

    # Optional: Show a message box to confirm backup completion
    messagebox.showinfo("Backup Complete", f"Database backup created: {backup_name}")


def export_group_to_pdf(group_name):
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()

    # Current year + month
    year = now.year
    month = now.month
    now = datetime.now()
    timestamp = now.strftime("%Y_%m_%d")

    # Query students + pay status for current month
    c.execute("""
        SELECT s.id, s.name,
               COALESCE(p.paid, 'Unpaid') AS pay_status
        FROM students s
        JOIN student_group sg ON s.id = sg.student_id
        JOIN groups g ON sg.group_id = g.id
        LEFT JOIN payments p 
            ON s.id = p.student_id AND p.year = ? AND p.month = ?
        WHERE g.name = ?
        ORDER BY s.name
    """, (year, month, group_name))

    rows = c.fetchall()
    conn.close()

    if not rows:
        messagebox.showinfo("No Data", f"No students found in group '{group_name}' for {timestamp}.")
        return

    # Create export folder
    os.makedirs("exports", exist_ok=True)
    filename = os.path.join("exports", f"group_{group_name.replace(' ', '_')}_{timestamp}.pdf")

    # Create PDF
    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # Title
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawString(50, height - 50, f"El Najah School")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, height - 80, f"Group: {group_name} ({timestamp})")

    # Table header
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, height - 120, "ID")
    pdf.drawString(150, height - 120, "Name")
    pdf.drawString(400, height - 120, "Pay Status")

    # Table rows
    y = height - 160
    pdf.setFont("Helvetica", 12)
    for sid, name, pay_status in rows:
        pdf.drawString(50, y, str(sid))
        pdf.drawString(150, y, name)
        pdf.drawString(400, y, pay_status)
        y -= 20
        if y < 50:  # new page
            pdf.showPage()
            y = height - 50

    pdf.save()
    messagebox.showinfo("Export Complete", f"PDF saved: {filename}")

def export_student_payment_history_pdf():
    """
    Prompt for Student ID and Academic Year (e.g. 2024 for 2024-2025),
    then export Aug(year) -> Jul(year+1) payment history for that student to PDF.
    """
    # helper: compute default academic year
    def current_academic_year_from_today():
        now = datetime.now()
        return now.year if now.month >= 8 else now.year - 1

    # helper: build ordered months for an academic year
    def months_for_academic_year(academic_year):
        months_names = ["January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November", "December"]
        order = []
        # Aug..Dec => academic_year
        for m in range(8, 13):
            order.append((f"{months_names[m-1]} {academic_year}", academic_year, m))
        # Jan..Jul => academic_year + 1
        for m in range(1, 8):
            order.append((f"{months_names[m-1]} {academic_year+1}", academic_year+1, m))
        return order

    # Ask for student ID
    sid_text = simpledialog.askstring("Export Student History", "Enter Student ID (number):", parent=ElNajahSchool)
    if sid_text is None:
        return  # user cancelled
    sid_text = sid_text.strip()
    if not sid_text.isdigit():
        messagebox.showerror("Invalid ID", "Student ID must be a number.")
        return
    student_id = int(sid_text)

    # Verify student exists
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("SELECT name FROM students WHERE id = ?", (student_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        messagebox.showerror("Not found", f"Student ID {student_id} was not found.")
        return
    student_name = row[0]

    # Ask for academic year (start year)
    default_year = current_academic_year_from_today()
    year_text = simpledialog.askstring("Academic Year",
                                       f"Enter academic START year (e.g. {default_year} for {default_year}-{default_year+1}):",
                                       initialvalue=str(default_year),
                                       parent=ElNajahSchool)
    if year_text is None:
        conn.close()
        return
    year_text = year_text.strip()
    if not year_text.isdigit():
        conn.close()
        messagebox.showerror("Invalid Year", "Year must be a number, e.g. 2024.")
        return
    academic_year = int(year_text)

    # Build months
    months = months_for_academic_year(academic_year)

    # Fetch records for each month (latest payment row if any)
    history_rows = []
    try:
        for label, y, mnum in months:
            c.execute("""
                SELECT paid, payment_date
                FROM payments
                WHERE student_id = ? AND year = ? AND month = ?
                ORDER BY payment_date DESC
                LIMIT 1
            """, (student_id, y, mnum))
            pr = c.fetchone()
            if pr is None:
                status = "unpaid"   # per your spec: treat missing as unpaid for export
                pdate = "—"
            else:
                paid_val, pdate_val = pr
                if paid_val is None:
                    status = "unpaid"
                else:
                    status = paid_val  # 'paid' or 'unpaid'
                pdate = pdate_val if pdate_val else "—"
            history_rows.append((label, status, pdate))
    finally:
        conn.close()

    # Confirm / let user pick filename location (optional)
    os.makedirs("exports", exist_ok=True)
    default_filename = f"exports/student_{student_id}_{student_name}_{academic_year}-{academic_year+1}_{datetime.now().strftime('%Y_%m_%d')}.pdf"
    save_path = filedialog.asksaveasfilename(
        title="Save payment history PDF",
        initialdir=os.path.abspath("exports"),
        initialfile=os.path.basename(default_filename),
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")],
        parent=ElNajahSchool
    )
    if not save_path:
        # user cancelled save dialog
        return

    # Create simple portrait A4 PDF with header + table (Month | Status | Payment Date)
    pdf = canvas.Canvas(save_path, pagesize=A4)
    page_w, page_h = A4
    left = 40
    right = 40
    top = 40
    y = page_h - top

    # Header
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, "El Najah School")
    y -= 22
    pdf.setFont("Helvetica", 12)
    pdf.drawString(left, y, f"Student Payment History")
    y -= 16
    pdf.setFont("Helvetica", 11)
    pdf.drawString(left, y, f"Student ID: {student_id}    Name: {student_name}")
    y -= 14
    pdf.drawString(left, y, f"Academic Year: {academic_year}-{academic_year+1}")
    y -= 20

    # Table header
    pdf.setFont("Helvetica-Bold", 11)
    col1_x = left
    col2_x = left + 200
    col3_x = left + 340
    pdf.drawString(col1_x, y, "Month")
    pdf.drawString(col2_x, y, "Status")
    pdf.drawString(col3_x, y, "Payment Date")
    y -= 14
    pdf.line(left, y + 9.5, page_w - right, y + 9.5)
    pdf.setFont("Helvetica", 11)

    # Rows
    line_height = 14
    for label, status, pdate in history_rows:
        if y - line_height < 40:
            pdf.showPage()
            y = page_h - top
            # redraw header on new page
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawString(col1_x, y, "Month")
            pdf.drawString(col2_x, y, "Status")
            pdf.drawString(col3_x, y, "Payment Date")
            y -= 16
            pdf.line(left, y + 6, page_w - right, y + 6)
            pdf.setFont("Helvetica", 11)

        pdf.drawString(col1_x, y, label)
        pdf.drawString(col2_x, y, status)
        pdf.drawString(col3_x, y, pdate)
        y -= line_height

    # Footer / generated on
    if y - 40 < 0:
        pdf.showPage()
        y = page_h - top
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(left, 30, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    pdf.save()
    messagebox.showinfo("Export Complete", f"PDF saved to:\n{save_path}", parent=ElNajahSchool)


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

        # Delete payments for those students (safety if cascade isn't working)
        student_ids = [str(sid) for sid, _ in groupless]
        placeholders = ",".join("?" for _ in student_ids)

        c.execute(f"DELETE FROM payments WHERE student_id IN ({placeholders})", student_ids)

        # Delete students
        c.execute(f"DELETE FROM students WHERE id IN ({placeholders})", student_ids)

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
        SELECT s.id, s.name, GROUP_CONCAT(g.name)
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
    now = datetime.now()
    timestamp = now.strftime("%Y_%m_%d")
    export_dir = "exports"
    os.makedirs("exports", exist_ok=True)
    filename = os.path.join("exports", "all_students_" + timestamp + ".xlsx")

    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"

    # Header row
    ws.append(["ID", "Name", "Groups"])

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

def send_feedback():
    # Replace with your email
    your_email = "ywkouamb@gmail.com"
    subject = "El Najah School Feedback"
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
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()

    # 1. Find duplicate names
    c.execute("""
        SELECT name, COUNT(*) as cnt
        FROM students
        GROUP BY name
        HAVING cnt > 1
    """)
    duplicates = c.fetchall()

    if not duplicates:
        messagebox.showinfo("Merge Duplicates", "No duplicate students found.")
        conn.close()
        return

    # 2. Build modal window
    top = ctk.CTkToplevel(ElNajahSchool)
    top.title("Merge Duplicate Students")
    top.geometry("500x400")
    top.grab_set()

    frame = ctk.CTkScrollableFrame(top, width=480, height=300)
    frame.pack(padx=10, pady=10, fill="both", expand=True)

    selected_keep = {}  # map name → tk.IntVar()

    # 3. For each duplicate name, show options
    for name, _ in duplicates:
        c.execute("""
            SELECT s.id, s.name, 
                   COALESCE(GROUP_CONCAT(g.name), '—') as groups
            FROM students s
            LEFT JOIN student_group sg ON s.id = sg.student_id
            LEFT JOIN groups g ON sg.group_id = g.id
            WHERE s.name = ?
            GROUP BY s.id
            ORDER BY s.id
        """, (name,))
        records = c.fetchall()

        if len(records) < 2:
            continue

        label = ctk.CTkLabel(frame, text=f"Duplicate: {name}", font=("Arial", 14, "bold"))
        label.pack(anchor="w", pady=(10, 0))

        var = tk.IntVar(value=records[0][0])  # default keep = first ID
        selected_keep[name] = var

        for sid, sname, groups in records:
            rb = ctk.CTkRadioButton(
                frame,
                text=f"ID {sid} | {sname} | Groups: {groups}",
                variable=var,
                value=sid
            )
            rb.pack(anchor="w")

    # 4. Merge action
    def confirm_merge():
        try:
            for name, var in selected_keep.items():
                keep_id = var.get()

                # find all other IDs
                c.execute("SELECT id FROM students WHERE name = ? AND id != ?", (name, keep_id))
                merge_ids = [row[0] for row in c.fetchall()]

                for mid in merge_ids:
                    # Move payments
                    c.execute("""
                        INSERT OR IGNORE INTO payments (student_id, year, month, paid, payment_date)
                        SELECT ?, year, month, paid, payment_date
                        FROM payments WHERE student_id = ?
                    """, (keep_id, mid))

                    # Move groups
                    c.execute("""
                        INSERT OR IGNORE INTO student_group (student_id, group_id)
                        SELECT ?, group_id
                        FROM student_group WHERE student_id = ?
                    """, (keep_id, mid))

                    # Delete old student
                    c.execute("DELETE FROM students WHERE id = ?", (mid,))

            conn.commit()
            messagebox.showinfo("Merge Complete", "Duplicate students successfully merged.")
            refresh_treeview_all()
            top.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", str(e))

        finally:
            conn.close()  # ✅ only close here

    btn = ctk.CTkButton(top, text="Merge Selected", command=confirm_merge)
    btn.pack(pady=10)



def bulk_remove_group_if_only_group():
    groups = get_all_groups()
    if not groups:
        messagebox.showinfo("No Groups", "There are no groups in the database.")
        return

    # Ask user to choose group
    top = ctk.CTkToplevel(ElNajahSchool)
    top.title("Bulk Remove Group")
    top.geometry("360x160")
    top.grab_set(); top.focus_force()

    ctk.CTkLabel(top, text="Select a group to remove (only if sole group):", font=("Arial", 14)).pack(pady=(12,6))

    selected_group = ctk.StringVar(value=groups[0])
    option = ctk.CTkOptionMenu(top, values=groups, variable=selected_group)
    option.pack(pady=6, padx=12, fill='x')

    def confirm_bulk_remove():
        group_name = selected_group.get()
        if not messagebox.askyesno("Confirm", f"Delete group '{group_name}' (remove from sole students, and delete group if empty)?"):
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

            # --- Case 1: Group has no students at all ---
            c.execute("SELECT COUNT(*) FROM student_group WHERE group_id = ?", (group_id,))
            if c.fetchone()[0] == 0:
                c.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                conn.commit()
                refresh_treeview_all()
                # refresh OptionMenu
                option.configure(values=get_all_groups())
                if get_all_groups():
                    selected_group.set(get_all_groups()[0])
                else:
                    top.destroy()
                messagebox.showinfo("Group Deleted", f"Group '{group_name}' was deleted (no students).")
                return

            # --- Case 2: Group has students ---
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

            # Remove group links for those students
            if students_to_remove:
                c.executemany(
                    "DELETE FROM student_group WHERE student_id = ? AND group_id = ?", 
                    [(sid, group_id) for sid in students_to_remove]
                )
                conn.commit()

                # Cleanup groupless students
                delete_groupless_students()

            # Check if group became empty
            c.execute("SELECT 1 FROM student_group WHERE group_id = ? LIMIT 1", (group_id,))
            if not c.fetchone():
                c.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                conn.commit()

            refresh_treeview_all()

            # refresh OptionMenu after deletion
            option.configure(values=get_all_groups())
            if get_all_groups():
                selected_group.set(get_all_groups()[0])
            else:
                top.destroy()

            messagebox.showinfo(
                "Bulk Remove Complete", 
                f"Group '{group_name}' processed.\n"
                f"- Removed from {len(students_to_remove)} student(s).\n"
                f"- Groupless students auto deleted.\n"
                f"- Group deleted if empty."
            )

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()

    btn_frame = ctk.CTkFrame(top, fg_color="transparent")
    btn_frame.pack(pady=8, padx=12, fill='x')
    ctk.CTkButton(btn_frame, text="Remove", command=confirm_bulk_remove).pack(side='left', padx=6)
    ctk.CTkButton(btn_frame, text="Cancel", command=top.destroy).pack(side='left', padx=6)



def export_unpaid_students_pdf():
    year = now.year
    month = now.month
    

    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT g.name AS group_name, s.name AS student_name
        FROM students s
        JOIN student_group sg ON s.id = sg.student_id
        JOIN groups g ON sg.group_id = g.id
        LEFT JOIN payments p 
            ON p.student_id = s.id AND p.year = ? AND p.month = ?
        WHERE p.id IS NULL OR p.paid = 'unpaid'
        ORDER BY g.name, s.name
    """, (year, month))
    rows = c.fetchall()
    conn.close()

    if not rows:
        messagebox.showinfo("No Unpaid", f"No unpaid students found for {year}-{month:02d}.")
        return

    # Prepare filename
    os.makedirs("exports", exist_ok=True)
    filename = os.path.join("exports", f"unpaid_students_{year}-{month:02d}.pdf")

    # Create PDF
    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, height - 50, f"Unpaid Students Report - {year}-{month:02d}")

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

        if y < 50:  # New page
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
    pdf_path = os.path.join(export_folder, f"student_count_{timestamp}.pdf")

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

# === Tool Bar (still standard Tk) ===
tools_menu = Menu(menubar, tearoff=0)
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
Export_menu.add_command(label="Export Student Payment History to PDF", command=export_student_payment_history_pdf)
menubar.add_cascade(label="Export", menu=Export_menu)

# === Help Menu (still standard Tk) ===
help_menu = Menu(menubar, tearoff=0)
help_menu.add_command(label="Contact Support", command=contact_support)
help_menu.add_command(label="Send Feedback", command=send_feedback)
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

    if year is None or month is None:
        from datetime import datetime
        now = datetime.now()
        year, month = now.year, now.month

    # Build a YYYY-MM-DD for the selected period (use day=1 always)
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
    now = datetime.now()
    current_year = now.year
    current_month = now.month  # 1-12

    sql = """
        SELECT s.id, s.name,
               COALESCE(GROUP_CONCAT(g.name), '—') AS groups,
               COALESCE(p.paid, 'No record') AS monthly_payment
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        LEFT JOIN payments p
               ON s.id = p.student_id AND p.year = ? AND p.month = ?
        GROUP BY s.id
        ORDER BY s.id ASC
    """
    _update_tree_from_query(sql, (current_year, current_month))



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
    now = datetime.now()
    current_year = now.year
    current_month = now.month  # 1-12

    sql = """
        SELECT s.id, s.name,
               COALESCE(GROUP_CONCAT(g.name), '—') AS groups,
               COALESCE(p.paid, 'No record') AS monthly_payment
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        LEFT JOIN payments p
               ON s.id = p.student_id AND p.year = ? AND p.month = ?
        GROUP BY s.id
        ORDER BY s.name COLLATE NOCASE ASC
    """
    _update_tree_from_query(sql, (current_year, current_month))


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

# paymants logs 
def open_full_window():
    import json
    from datetime import datetime
    import sqlite3
    import os
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from tkinter import filedialog

    # prefs file for remembering last year/group
    PREFS_FILE = "prefs.json"

    def load_prefs():
        if os.path.exists(PREFS_FILE):
            try:
                with open(PREFS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_prefs(p):
        try:
            with open(PREFS_FILE, "w", encoding="utf-8") as f:
                json.dump(p, f)
        except Exception:
            pass

    # academic year helpers
    def current_academic_year_from_today():
        now = datetime.now()
        # if month >= Aug -> academic year = current year, else previous year
        return now.year if now.month >= 8 else now.year - 1

    def months_for_academic_year(academic_year):
        months_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        order = []
        for m in range(8, 13):
            label = months_names[m - 1]
            order.append((label + " " + str(academic_year), academic_year, m))
        for m in range(1, 8):
            label = months_names[m - 1]
            order.append((label + " " + str(academic_year + 1), academic_year + 1, m))
        return order

    # prepare window
    full_win = ctk.CTkToplevel(ElNajahSchool)
    full_win.title("Payments History Logs")
    full_win.state("zoomed")
    full_win.geometry(f"{ElNajahSchool.winfo_screenwidth()}x{ElNajahSchool.winfo_screenheight()}+0+0")
    full_win.grab_set()

    # Title
    title_label = ctk.CTkLabel(full_win, text="Payments History", font=("Arial", 30, "bold"))
    title_label.pack(pady=(0, 10))

    # load prefs
    prefs = load_prefs()
    default_academic = prefs.get("last_academic_year", current_academic_year_from_today())
    default_group = prefs.get("last_group", None)

    # top selectors row
    sel_frame = ctk.CTkFrame(full_win, fg_color="transparent")
    sel_frame.pack(pady=10, anchor="center")

    now_year = datetime.now().year
    years = [str(y) for y in range(now_year - 6, now_year + 6)]
    year_var = ctk.StringVar(value=str(default_academic))
    group_names = get_all_groups()
    if not group_names:
        group_names = ["(no groups)"]
    group_var = ctk.StringVar(value=default_group or group_names[0])

    # grid layout for compact row
    sel_frame.grid_columnconfigure(0, weight=0)
    sel_frame.grid_columnconfigure(1, weight=0)
    sel_frame.grid_columnconfigure(2, weight=0)
    sel_frame.grid_columnconfigure(3, weight=0)
    sel_frame.grid_columnconfigure(4, weight=0)

    ctk.CTkLabel(sel_frame, text="Academic Year:", font=("Arial", 14)).grid(row=0, column=0, padx=6)
    year_option = ctk.CTkOptionMenu(sel_frame, values=years, variable=year_var)
    year_option.grid(row=0, column=1, padx=6)

    ctk.CTkLabel(sel_frame, text="Group:", font=("Arial", 14)).grid(row=0, column=2, padx=6)
    group_option = ctk.CTkOptionMenu(sel_frame, values=group_names, variable=group_var)
    group_option.grid(row=0, column=3, padx=6)

    # actions
    actions_frame = ctk.CTkFrame(sel_frame, fg_color="transparent")
    actions_frame.grid(row=0, column=4, padx=6)

    def action_export_pdf():
        export_current_view_pdf()
    def action_refresh():
        refresh_full_tree()
    def action_close():
        prefs["last_academic_year"] = int(year_var.get())
        prefs["last_group"] = group_var.get()
        save_prefs(prefs)
        full_win.destroy()

    ctk.CTkButton(actions_frame, text="Export PDF", command=action_export_pdf).pack(side="left", padx=4)
    def on_edit_payment_click():
        sel = tree_full.selection()
        if not sel:
            messagebox.showerror("No selection", "Select a student first.")
            return
        vals = tree_full.item(sel[0], "values")
        try:
            student_id = int(vals[0])
        except Exception:
            messagebox.showerror("Error", "Could not read student ID from the table.")
            return

        # Optional: pass a refresher so your history/main view updates after Save.
        # Replace 'refresh_payment_history_for' with your real function if you have one.
        def _after_save(_sid):
            try:
                # Example: if you have a function that redraws the payment history for selected student
                # refresh_payment_history_for(_sid)
                pass
            except Exception:
                pass

        open_edit_payment_modal(student_id, on_saved=_after_save)

    ctk.CTkButton(actions_frame,text="Edit Payment",fg_color="#43C24E",command=on_edit_payment_click).pack(side="left", padx=4)
    ctk.CTkButton(actions_frame, text="Refresh", command=action_refresh).pack(side="left", padx=4)
    ctk.CTkButton(actions_frame, text="Close", fg_color="#F13D3D", command=action_close).pack(side="left", padx=4)

    # Separator
    sep = ttk.Separator(full_win, orient="horizontal")
    sep.pack(fill="x", pady=5)

    # Treeview area
    tree_frame = ctk.CTkFrame(full_win, fg_color="transparent")
    tree_frame.pack(fill="both", expand=True)

    tv_columns = ["id", "name"]  # will add month headers dynamically
    tree_full = ttk.Treeview(tree_frame, columns=tv_columns, show="headings", style="Full.Treeview")
    tree_full.pack(side="left", fill="both", expand=True)

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree_full.yview)
    vsb.pack(side="right", fill="y")
    tree_full.configure(yscrollcommand=vsb.set)

    style = ttk.Style()
    style.configure("Full.Treeview", rowheight=28)
    tree_full.tag_configure("evenrow", background="#f2f2f2")
    tree_full.tag_configure("oddrow", background="#ffffff")


    # helper to map columns and refresh
    def build_month_headers_and_columns(academic_year):
        nonlocal tv_columns
        months = months_for_academic_year(int(academic_year))
        # rebuild tv_columns
        tv_columns = ["id", "name"] + [m[0] for m in months]  # labels as column ids (unique)
        # clear existing tree columns
        tree_full["columns"] = tv_columns
        # configure headings & widths
        tree_full.heading("id", text="ID")
        tree_full.column("id", width=60, anchor="center")
        tree_full.heading("name", text="Name")
        tree_full.column("name", width=150, anchor="w")
        # month columns
        for label, y, mnum in months:
            tree_full.heading(label, text=label)
            tree_full.column(label, width=80, anchor="center")

        return months  # return month tuples list

    # build initial headers
    months_list = build_month_headers_and_columns(year_var.get())

    # function to fetch rows for selected group & academic year
    def get_students_for_group(group_name):
        conn = sqlite3.connect("elnajah.db")
        c = conn.cursor()
        try:
            c.execute("""
                SELECT s.id, s.name
                FROM students s
                JOIN student_group sg ON s.id = sg.student_id
                JOIN groups g ON sg.group_id = g.id
                WHERE g.name = ?
                ORDER BY s.id ASC
            """, (group_name,))
            return c.fetchall()
        finally:
            conn.close()

    # helper to fetch payment latest record for a student/year/month
    def fetch_payment(student_id, year, month):
        conn = sqlite3.connect("elnajah.db")
        c = conn.cursor()
        try:
            c.execute("""
                SELECT paid, payment_date
                FROM payments
                WHERE student_id = ? AND year = ? AND month = ?
                ORDER BY payment_date DESC
                LIMIT 1
            """, (student_id, year, month))
            return c.fetchone()  # (paid, payment_date) or None
        finally:
            conn.close()

    # populate tree
    def refresh_full_tree():
        nonlocal months_list
        tree_full.delete(*tree_full.get_children())

        # rebuild headers if year changed
        months_list = build_month_headers_and_columns(year_var.get())

        group_name = group_var.get()
        if group_name == "(no groups)":
            return

        students = get_students_for_group(group_name)

        conn = sqlite3.connect("elnajah.db")
        c = conn.cursor()

        for i, (sid, name) in enumerate(students):
            # fetch join_date once for the student
            c.execute("SELECT join_date FROM students WHERE id = ?", (sid,))
            row = c.fetchone()
            join_date = row[0] if row else None

            row_values = [sid, name]

            for label, y, mnum in months_list:
                pr = fetch_payment(sid, y, mnum)

                if join_date:
                    join_dt = datetime.strptime(join_date, "%Y-%m-%d")

                    if (y < join_dt.year) or (y == join_dt.year and mnum < join_dt.month):
                        # Before the join month → no record
                        row_values.append("no record")
                    else:
                        # Same month or after → normal check
                        if pr is None:
                            row_values.append("Unpaid")
                        else:
                            paid, pdate = pr
                            row_values.append(paid if paid else "Unpaid")
                else:
                    # If join_date missing, default to unpaid if no record
                    if pr is None:
                        row_values.append("Unpaid")
                    else:
                        paid, pdate = pr
                        row_values.append(paid if paid else "Unpaid")

            # 👇 these lines must be inside the loop
            tags = ("evenrow" if i % 2 == 0 else "oddrow",)
            tree_full.insert("", "end", values=row_values, tags=tags)

        conn.close()



    # toggle logic when clicking a month cell
    def on_tree_click(ev):
        # need to identify region & column & row
        region = tree_full.identify_region(ev.x, ev.y)
        if region != "cell":
            return
        col = tree_full.identify_column(ev.x)  # like '#1'
        row_id = tree_full.identify_row(ev.y)
        if not row_id:
            return
        try:
            col_idx = int(col.replace("#", "")) - 1  # 0-based
        except Exception:
            return
        # columns: 0 => id, 1 => name, 2.. => months
        if col_idx < 2:
            return  # do nothing for id/name
        values = tree_full.item(row_id, "values")
        if not values:
            return
        student_id = int(values[0])
        # determine month tuple
        month_index = col_idx - 2
        if month_index < 0 or month_index >= len(months_list):
            return
        _, year_for_cell, month_for_cell = months_list[month_index]

        # fetch existing payment
        conn = sqlite3.connect("elnajah.db")
        c = conn.cursor()
        try:
            c.execute("""
                SELECT id, paid FROM payments
                WHERE student_id = ? AND year = ? AND month = ?
                ORDER BY payment_date DESC
                LIMIT 1
            """, (student_id, year_for_cell, month_for_cell))
            row = c.fetchone()
            nowstr = datetime.now().strftime("%Y-%m-%d")
            if row is None:
                # no record -> insert paid (as toggle behavior)
                c.execute("""
                    INSERT INTO payments (student_id, year, month, paid, payment_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, year_for_cell, month_for_cell, "paid", nowstr))
            else:
                pid, paid = row
                if paid == "paid":
                    # set to unpaid (update)
                    c.execute("""
                        UPDATE payments SET paid = ?, payment_date = ? WHERE id = ?
                    """, ("unpaid", nowstr, pid))
                else:
                    # set to paid
                    c.execute("""
                        UPDATE payments SET paid = ?, payment_date = ? WHERE id = ?
                    """, ("paid", nowstr, pid))
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("DB Error", str(e))
        finally:
            conn.close()

        # refresh the row or entire tree
        refresh_full_tree()

    tree_full.bind("<Button-1>", on_tree_click)

    # handler when year or group changes
    def on_year_or_group_change(*_):
        # update group option menu values (in case groups changed)
        current_groups = get_all_groups()
        if current_groups:
            group_option.configure(values=current_groups)
            # if selected group not in list, set to first
            if group_var.get() not in current_groups:
                group_var.set(current_groups[0])
        # save prefs
        prefs["last_academic_year"] = int(year_var.get())
        prefs["last_group"] = group_var.get()
        save_prefs(prefs)
        # refresh tree
        refresh_full_tree()

    year_var.trace_add("write", on_year_or_group_change)
    group_var.trace_add("write", on_year_or_group_change)

    # initial population
    refresh_full_tree()

    # Export current view to PDF (includes payment_date if paid)
    def export_current_view_pdf():
        import os
        import textwrap
        import sqlite3
        from datetime import datetime
        from tkinter import messagebox
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import landscape, A4

        # === Prepare rows with month data as (status, date) tuples ===
        rows = []
        headers = ["ID", "Name"] + [label for label, _, _ in months_list]

        for iid in tree_full.get_children():
            vals = tree_full.item(iid, "values")
            sid = int(vals[0])
            row = [vals[0], vals[1]]

            # fetch join_date once
            conn = sqlite3.connect("elnajah.db")
            c = conn.cursor()
            c.execute("SELECT join_date FROM students WHERE id = ?", (sid,))
            join_row = c.fetchone()
            conn.close()
            join_date = join_row[0] if join_row else None
            join_dt = datetime.strptime(join_date, "%Y-%m-%d") if join_date else None

            for label, y, mnum in months_list:
                pr = fetch_payment(sid, y, mnum)

                if join_dt and (y < join_dt.year or (y == join_dt.year and mnum < join_dt.month)):
                    row.append(("no record", ""))
                else:
                    if pr is None:
                        row.append(("Unpaid", ""))
                    else:
                        paid, pdate = pr
                        if paid == "paid":
                            row.append(("Paid", pdate))
                        elif paid == "unpaid":
                            row.append(("Unpaid", ""))
                        else:
                            row.append(("no record", ""))

            rows.append(row)

        if not rows:
            messagebox.showinfo("No Data", "Nothing to export.")
            return

        # === PDF Setup ===
        os.makedirs("exports", exist_ok=True)
        ts = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        filename = os.path.join("exports", f"payments_{group_var.get()}_{year_var.get()}_{ts}.pdf")

        page_size = landscape(A4)
        pdf = canvas.Canvas(filename, pagesize=page_size)
        page_w, page_h = page_size

        left_margin, right_margin, top_margin, bottom_margin = 30, 30, 40, 40
        row_padding, line_height = 6, 11

        # === Dynamic Column Widths ===
        available = page_w - left_margin - right_margin
        n_months = len(months_list)
        id_min, id_pref = 35, 70
        name_min, name_pref = 70, 250
        month_min = 60

        id_w = id_pref
        name_w = name_pref
        remaining = available - (id_w + name_w)
        month_base = max(month_min, remaining // n_months if n_months else 0)
        col_widths = [id_w, name_w] + [month_base] * n_months

        # Adjust if widths exceed available space
        total_w = sum(col_widths)
        if total_w > available:
            # shrink Name first
            overflow = total_w - available
            name_w = max(name_min, name_w - overflow)
            col_widths[1] = name_w
            total_w = sum(col_widths)
            if total_w > available:
                # shrink ID if still overflow
                overflow = total_w - available
                id_w = max(id_min, id_w - overflow)
                col_widths[0] = id_w

        # Recalculate month widths if leftover space
        leftover = available - sum(col_widths)
        if leftover > 0:
            col_widths[-1] += leftover  # add to last month column

        col_x = [left_margin]
        for w in col_widths[:-1]:
            col_x.append(col_x[-1] + w)

        # === Title and headers ===
        pdf.setFont("Helvetica-Bold", 14)
        title = f"Payments — Group: {group_var.get()} — Academic Year: {year_var.get()}"
        pdf.drawString(left_margin, page_h - top_margin + 10, title)
        pdf.setFont("Helvetica-Bold", 10)

        y = page_h - top_margin - 10
        for i, hdr in enumerate(headers):
            pdf.drawString(col_x[i] + 2, y, str(hdr))
        y -= 16
        pdf.setFont("Helvetica", 9)

        def draw_header_on_new_page():
            nonlocal y
            pdf.setFont("Helvetica-Bold", 10)
            y = page_h - top_margin - 10
            for i, hdr in enumerate(headers):
                pdf.drawString(col_x[i] + 2, y, str(hdr))
            y -= 16
            pdf.setFont("Helvetica", 9)

        def max_chars_for_width(w):
            return max(8, int((w - 6) // 6))

        # === Draw rows ===
        for row in rows:
            # Name wrapping
            name_text = str(row[1])
            name_max_chars = max_chars_for_width(col_widths[1])
            name_lines = textwrap.wrap(name_text, width=name_max_chars) or [""]

            # Determine max lines for this row (name vs 2-line months)
            row_height = max(line_height * len(name_lines), line_height * 2) + row_padding

            if y - row_height < bottom_margin:
                pdf.showPage()
                draw_header_on_new_page()

            # Draw ID
            pdf.drawString(col_x[0] + 2, y, str(row[0]))

            # Draw Name
            for li, ln in enumerate(name_lines):
                pdf.drawString(col_x[1] + 2, y - (li * line_height), ln)

            # Draw Month cells (status + date)
            for i in range(n_months):
                status, date = row[2 + i]
                pdf.drawString(col_x[2 + i] + 2, y, status)
                if date:
                    pdf.drawString(col_x[2 + i] + 2, y - line_height, date)

            y -= row_height

        pdf.save()
        messagebox.showinfo("Export Complete", f"PDF saved:\n{filename}")
import sqlite3
from datetime import datetime, date
from tkinter import messagebox
import customtkinter as ctk

# ---------- DB HELPERS ----------



def get_student_info(student_id: int):
    """
    Returns (id, name, groups_text, join_dt or None)
    """
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT s.id, s.name, s.join_date, COALESCE(GROUP_CONCAT(g.name), '—') AS groups
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        WHERE s.id = ?
        GROUP BY s.id
    """, (student_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    sid, name, join_date_str, groups = row
    join_dt = None
    if join_date_str:
        try:
            join_dt = datetime.strptime(join_date_str, "%Y-%m-%d").date()
        except Exception:
            join_dt = None
    return sid, name, groups, join_dt

def get_academic_year_options(window=2):
    """
    Returns a list like ['2023–2024', '2024–2025', '2025–2026'] centered around current AY.
    AY starts in August.
    """
    today = date.today()
    start_year = today.year if today.month >= 8 else today.year - 1
    options = []
    for delta in range(-window, window + 1):
        sy = start_year + delta
        options.append(f"{sy}–{sy+1}")
    return options

def split_academic_label(label: str):
    """
    '2024–2025' -> (2024, 2025)
    """
    # Handle both en dash and hyphen to be robust
    lab = label.replace("–", "-")
    parts = lab.split("-")
    sy = int(parts[0])
    ey = int(parts[1])
    return sy, ey

def months_for_academic_year(start_year: int):
    """
    Returns a list of tuples for Aug..Dec of start_year and Jan..Jul of next year.
    Each tuple: (label, year, month)
    Labels like 'Aug 2024', 'Jan 2025'
    """
    months_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    lst = []
    # Aug(8)..Dec(12) of start_year
    for m in range(8, 13):
        lst.append((f"{months_names[m-1]} {start_year}", start_year, m))
    # Jan(1)..Jul(7) of start_year+1
    for m in range(1, 8):
        lst.append((f"{months_names[m-1]} {start_year+1}", start_year+1, m))
    return lst

def get_payments_for_academic_year(student_id: int, start_year: int):
    """
    Returns dict {(year, month): (paid, payment_date)} for the AY.
    """
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT year, month, paid, payment_date
        FROM payments
        WHERE student_id = ?
          AND (
                (year = ? AND month BETWEEN 8 AND 12)
             OR (year = ? AND month BETWEEN 1 AND 7)
          )
    """, (student_id, start_year, start_year+1))
    rows = c.fetchall()
    conn.close()
    out = {}
    for yr, mo, paid, pdate in rows:
        out[(yr, mo)] = (paid, pdate or "")
    return out

def upsert_payments_bulk(student_id: int, items: list):
    """
    items: list of dicts with keys: year, month, paid ('paid'|'unpaid'), payment_date ('' or 'YYYY-MM-DD')
    Uses UPSERT; falls back to REPLACE if needed.
    """
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        c.executemany("""
            INSERT INTO payments (student_id, year, month, paid, payment_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id, year, month)
            DO UPDATE SET paid=excluded.paid, payment_date=excluded.payment_date
        """, [(student_id, it["year"], it["month"], it["paid"], it["payment_date"]) for it in items])
    except sqlite3.OperationalError:
        # Fallback for older SQLite: REPLACE INTO (note: REPLACE changes row id; fine for this use)
        c.executemany("""
            REPLACE INTO payments (student_id, year, month, paid, payment_date)
            VALUES (?, ?, ?, ?, ?)
        """, [(student_id, it["year"], it["month"], it["paid"], it["payment_date"]) for it in items])
    conn.commit()
    conn.close()

def refresh_views_after_payment_update(student_id: int):
    pass
    """
    Best-effort refresh without breaking your app.
    - Tries to call a history refresh function if present.
    - Tries to re-run whatever main table uses.
    Wraps calls in try/except so nothing crashes if names differ.
    """
    try:
        # If you have a function that refreshes the history popup, call it here.
        refresh_payment_history_popup(student_id)  # noqa: F821
    except Exception:
        pass
    try:
        # If you have a function that reloads the main tree, call it here.
        # Example: re-run current filter or query function.
        reload_current_view()  # noqa: F821
    except Exception:
        pass




# ---------- MODAL ----------

def open_edit_student_payment_modal(student_id: int = None):
    """
    Opens the Edit Payment modal for the selected student.
    - If student_id is None, tries to read it from the currently selected row in tree_full.
    """
    # Resolve student_id from selection if not provided
    # Resolve student_id from selection if not provided
    if student_id is None:
        sel = tree_full.selection()
        if not sel:
            sel = (tree_full.focus(),)
        if not sel or not sel[0]:
            messagebox.showerror("No selection", "Select a student first.")
            return

        vals = tree_full.item(sel[0], "values")
        if not vals:
            messagebox.showerror("Error", "Could not read student data from the table.")
            return
        student_id = int(vals[0])


    info = get_student_info(student_id)
    if not info:
        messagebox.showerror("Not found", f"Student {student_id} not found.")
        return

    sid, sname, sgroups, join_dt = info

    # Build modal
    win = ctk.CTkToplevel()
    win.title(f"Edit Payment — {sid} · {sname}")
    win.geometry("980x620")
    win.grab_set()  # modal behavior

    # --- Top: student info (read-only)
    top = ctk.CTkFrame(win)
    top.pack(fill="x", padx=12, pady=12)

    def add_info(label, value, col):
        lbl = ctk.CTkLabel(top, text=label, font=("", 12, "bold"))
        lbl.grid(row=0, column=col*2, sticky="w", padx=(8, 4), pady=(6, 2))
        val = ctk.CTkLabel(top, text=value, font=("", 12))
        val.grid(row=0, column=col*2 + 1, sticky="w", padx=(0, 12), pady=(6, 2))

    add_info("ID:", str(sid), 0)
    add_info("Name:", sname, 1)
    add_info("Groups:", sgroups, 2)
    add_info("Join Date:", join_dt.isoformat() if join_dt else "—", 3)
    top.grid_columnconfigure((1,3,5,7), weight=1)

    # --- Academic Year selector
    yr_frame = ctk.CTkFrame(win)
    yr_frame.pack(fill="x", padx=12, pady=(0, 10))
    ctk.CTkLabel(yr_frame, text="Academic Year", font=("", 12, "bold")).pack(side="left", padx=(8, 8))

    options = get_academic_year_options(window=2)
    # default = current AY
    default_ay = options[2]  # centered list, index 2
    ay_var = ctk.StringVar(value=default_ay)
    year_menu = ctk.CTkOptionMenu(yr_frame, variable=ay_var, values=options)
    year_menu.pack(side="left")

    # --- "Remaining Amount" (manual note)
    remaining_frame = ctk.CTkFrame(win)
    remaining_frame.pack(fill="x", padx=12, pady=(0, 6))
    ctk.CTkLabel(remaining_frame, text="Remaining Amount (note)", font=("", 12, "bold")).pack(side="left", padx=(8, 8))
    remaining_var = ctk.StringVar(value="")
    remaining_entry = ctk.CTkEntry(remaining_frame, textvariable=remaining_var, placeholder_text="manual note only")
    remaining_entry.pack(side="left", fill="x", expand=True)

    # --- Months Grid (2 rows x 6 cols)
    grid_frame = ctk.CTkFrame(win)
    grid_frame.pack(fill="both", expand=True, padx=12, pady=12)

    # State holders per month cell
    month_cells = []  # list of dicts: {frame, status_var, date_var, enabled, year, month, label}

    def validate_date_string(s: str) -> bool:
        if not s:
            return False
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return True
        except Exception:
            return False

    def build_grid():
        # clear previous
        for ch in grid_frame.winfo_children():
            ch.destroy()
        month_cells.clear()

        start_year, _ = split_academic_label(ay_var.get())
        months_spec = months_for_academic_year(start_year)
        existing = get_payments_for_academic_year(sid, start_year)

        # Build 12 cells
        for idx, (mlabel, yr, mo) in enumerate(months_spec):
            cell = ctk.CTkFrame(grid_frame, corner_radius=12)
            row = 0 if idx < 6 else 1
            col = idx if idx < 6 else idx - 6
            cell.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            # Make grid stretch
            grid_frame.grid_rowconfigure(row, weight=1)
            grid_frame.grid_columnconfigure(col, weight=1)

            # Header label
            ctk.CTkLabel(cell, text=mlabel, font=("", 12, "bold")).pack(anchor="w", padx=8, pady=(6, 2))

            # Determine if month is editable based on join date
            editable = True
            if join_dt:
                # Compare by year-month
                month_anchor = date(yr, mo, 1)
                if month_anchor < date(join_dt.year, join_dt.month, 1):
                    editable = False  # before join date => no radios/entry

            # Paid/Unpaid status var
            status_var = ctk.StringVar(value="unpaid")
            date_var = ctk.StringVar(value="")
            prev = existing.get((yr, mo))
            if prev:
                prev_status, prev_date = prev
                status_var.set(prev_status if prev_status in ("paid", "unpaid") else "unpaid")
                date_var.set(prev_date or "")
            else:
                # No record → default unpaid, date blank
                status_var.set("unpaid")
                date_var.set("")

            # radios
            rb_frame = ctk.CTkFrame(cell)
            rb_frame.pack(fill="x", padx=8, pady=(0, 4))
            rb_paid = ctk.CTkRadioButton(rb_frame, text="Paid", value="paid", variable=status_var)
            rb_unpd = ctk.CTkRadioButton(rb_frame, text="Unpaid", value="unpaid", variable=status_var)
            rb_paid.pack(side="left", padx=0)
            rb_unpd.pack(side="left")

            # date entry
            entry = ctk.CTkEntry(cell, textvariable=date_var, placeholder_text="YYYY-MM-DD")
            entry.pack(fill="x", padx=8, pady=(0, 8))

            # link behavior: when Paid selected & date empty → set today; when Unpaid → clear date
            def on_status_change(var=status_var, dvar=date_var):
                if var.get() == "paid":
                    if not dvar.get():
                        dvar.set(date.today().isoformat())
                else:
                    dvar.set("")

            status_var.trace_add("write", lambda *_args, f=on_status_change: f())

            # Enable/disable based on editable flag
            if not editable:
                rb_paid.configure(state="disabled")
                rb_unpd.configure(state="disabled")
                entry.configure(state="disabled")
                # Show info it is before join date
                ctk.CTkLabel(cell, text="No record (before join)", font=("", 11)).pack(anchor="w", padx=8, pady=(0, 6))

            month_cells.append({
                "frame": cell,
                "status_var": status_var,
                "date_var": date_var,
                "enabled": editable,
                "year": yr,
                "month": mo,
                "label": mlabel
            })

    build_grid()

    # Change of AY => rebuild
    def on_ay_change(choice):
        build_grid()
    year_menu.configure(command=on_ay_change)

    # --- Action buttons
    btn_frame = ctk.CTkFrame(win)
    btn_frame.pack(fill="x", padx=12, pady=(0, 12))
    btn_frame.grid_columnconfigure(0, weight=1)

    def on_cancel():
        win.destroy()

    def on_save():
        # Collect items; validate; then bulk UPSERT
        items = []
        invalid_cells = []
        for cell in month_cells:
            if not cell["enabled"]:
                continue  # months before join -> skip
            paid = cell["status_var"].get()
            pdate = cell["date_var"].get().strip()

            if paid == "paid":
                if not validate_date_string(pdate):
                    invalid_cells.append(cell["label"])
                items.append({
                    "year": cell["year"],
                    "month": cell["month"],
                    "paid": "paid",
                    "payment_date": pdate
                })
            else:
                # unpaid → force empty date (schema NOT NULL, empty string is fine)
                items.append({
                    "year": cell["year"],
                    "month": cell["month"],
                    "paid": "unpaid",
                    "payment_date": ""
                })

        if invalid_cells:
            messagebox.showerror(
                "Invalid dates",
                "Fix these month(s):\n" + "\n".join(invalid_cells) + "\n\nUse YYYY-MM-DD."
            )
            return

        try:
            upsert_payments_bulk(sid, items)
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to save payments.\n{e}")
            return

        # Best-effort refresh of other views
        try:
            refresh_views_after_payment_update(sid)
        except Exception:
            pass

        messagebox.showinfo("Saved", "Payments updated successfully.")
        win.destroy()

    btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", fg_color="#8E8E93", hover_color="#7A7A7E", command=on_cancel)
    btn_save = ctk.CTkButton(btn_frame, text="Save", fg_color="#43C24E", command=on_save)
    btn_cancel.pack(side="right", padx=(0, 8))
    btn_save.pack(side="right")


# ===== Edit Payment: DB + UI Helpers =====
import sqlite3
from datetime import datetime, date
from tkinter import messagebox
import customtkinter as ctk

# ---------- DB HELPERS ----------

def get_student_info(student_id: int):
    """
    Returns (id, name, groups_text, join_dt or None)
    """
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT s.id, s.name, s.join_date, COALESCE(GROUP_CONCAT(g.name), '—') AS groups
        FROM students s
        LEFT JOIN student_group sg ON s.id = sg.student_id
        LEFT JOIN groups g ON sg.group_id = g.id
        WHERE s.id = ?
        GROUP BY s.id
    """, (student_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    sid, name, join_date_str, groups = row
    join_dt = None
    if join_date_str:
        try:
            join_dt = datetime.strptime(join_date_str, "%Y-%m-%d").date()
        except Exception:
            join_dt = None
    return sid, name, groups, join_dt

def get_academic_year_options(window=2):
    """
    Return AY labels around current AY (AY starts in August).
    Example: ['2023–2024','2024–2025','2025–2026']
    """
    today = date.today()
    start_year = today.year if today.month >= 8 else today.year - 1
    opts = []
    for delta in range(-window, window + 1):
        sy = start_year + delta
        opts.append(f"{sy}–{sy+1}")
    return opts

def split_academic_label(label: str):
    """'2024–2025' or '2024-2025' -> (2024, 2025)"""
    lab = label.replace("–", "-")
    a, b = lab.split("-")
    return int(a), int(b)

def months_for_academic_year(start_year: int):
    """
    Aug..Dec of start_year + Jan..Jul of next year.
    -> list of (label, year, month)
    """
    short = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    out = []
    for m in range(8, 13):
        out.append((f"{short[m-1]} {start_year}", start_year, m))
    for m in range(1, 8):
        out.append((f"{short[m-1]} {start_year+1}", start_year+1, m))
    return out

def get_payments_for_academic_year(student_id: int, start_year: int):
    """
    {(year, month): (paid, payment_date)}
    """
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    c.execute("""
        SELECT year, month, paid, payment_date
        FROM payments
        WHERE student_id = ?
          AND (
                (year = ? AND month BETWEEN 8 AND 12)
             OR (year = ? AND month BETWEEN 1 AND 7)
          )
    """, (student_id, start_year, start_year+1))
    rows = c.fetchall()
    conn.close()
    d = {}
    for yr, mo, paid, pdate in rows:
        d[(yr, mo)] = (paid, pdate or "")
    return d

def upsert_payments_bulk(student_id: int, items: list):
    """
    items = [{year, month, paid('paid'|'unpaid'), payment_date(str)}]
    Uses UPSERT; falls back to REPLACE for older SQLite.
    """
    conn = sqlite3.connect("elnajah.db")
    c = conn.cursor()
    try:
        c.executemany("""
            INSERT INTO payments (student_id, year, month, paid, payment_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id, year, month)
            DO UPDATE SET paid=excluded.paid, payment_date=excluded.payment_date
        """, [(student_id, it["year"], it["month"], it["paid"], it["payment_date"]) for it in items])
    except sqlite3.OperationalError:
        c.executemany("""
            REPLACE INTO payments (student_id, year, month, paid, payment_date)
            VALUES (?, ?, ?, ?, ?)
        """, [(student_id, it["year"], it["month"], it["paid"], it["payment_date"]) for it in items])
    conn.commit()
    conn.close()

# Optional hook. Keep no-op to avoid Pylance warnings. Wire it later if you want auto-refresh.
def refresh_views_after_payment_update(_student_id: int):
    """No-op on purpose. Call your own refreshers here later if needed."""
    pass

# ---------- MODAL ----------

def open_edit_payment_modal(student_id: int, on_saved=None):
    """
    Edit Payment modal for one student.
    - Read-only: ID, Name, Groups, Join Date
    - AY selector (defaults to current AY)
    - 12 month grid (Aug..Jul): Paid/Unpaid radios + date entry
    - Months before join date are disabled ("No record (before join)")
    - Remaining Amount: manual note (not persisted)
    - Save writes all editable months; Cancel discards.
    - on_saved(sid) optional callback after successful save.
    """
    info = get_student_info(student_id)
    if not info:
        messagebox.showerror("Not found", f"Student {student_id} not found.")
        return
    sid, sname, sgroups, join_dt = info

    win = ctk.CTkToplevel()
    win.title(f"Edit Payment — {sid} · {sname}")
    win.geometry("980x620")
    win.grab_set()

    # --- Top: Student info (read-only)
    top = ctk.CTkFrame(win)
    top.pack(fill="x", padx=12, pady=12)

    def add_info(label, value, col):
        ctk.CTkLabel(top, text=label, font=("", 12, "bold")).grid(row=0, column=col*2, sticky="w", padx=(8, 4), pady=(6, 2))
        ctk.CTkLabel(top, text=value, font=("", 12)).grid(row=0, column=col*2 + 1, sticky="w", padx=(0, 12), pady=(6, 2))

    add_info("ID:", str(sid), 0)
    add_info("Name:", sname, 1)
    add_info("Groups:", sgroups, 2)
    add_info("Join Date:", join_dt.isoformat() if join_dt else "—", 3)
    top.grid_columnconfigure((1,3,5,7), weight=1)

    # --- Academic Year selector
    yr_frame = ctk.CTkFrame(win)
    yr_frame.pack(fill="x", padx=12, pady=(0, 10))
    ctk.CTkLabel(yr_frame, text="Academic Year", font=("", 12, "bold")).pack(side="left", padx=(8, 8))

    ay_options = get_academic_year_options(window=2)
    default_ay = ay_options[len(ay_options)//2]  # center = current AY
    ay_var = ctk.StringVar(value=default_ay)
    year_menu = ctk.CTkOptionMenu(yr_frame, variable=ay_var, values=ay_options)
    year_menu.pack(side="left")

    # --- Remaining Amount (manual note only)
    remaining_frame = ctk.CTkFrame(win)
    remaining_frame.pack(fill="x", padx=12, pady=(0, 6))
    ctk.CTkLabel(remaining_frame, text="Remaining Amount (note)", font=("", 12, "bold")).pack(side="left", padx=(8, 8))
    remaining_var = ctk.StringVar(value="")
    ctk.CTkEntry(remaining_frame, textvariable=remaining_var, placeholder_text="manual note only").pack(side="left", fill="x", expand=True)

    # --- Months Grid
    grid_frame = ctk.CTkFrame(win)
    grid_frame.pack(fill="both", expand=True, padx=12, pady=12)

    month_cells = []  # dicts: year, month, label, enabled, status_var, date_var

    def validate_date_string(s: str) -> bool:
        if not s:
            return False
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return True
        except Exception:
            return False

    def build_grid():
        for ch in grid_frame.winfo_children():
            ch.destroy()
        month_cells.clear()

        start_year, _ = split_academic_label(ay_var.get())
        spec = months_for_academic_year(start_year)
        existing = get_payments_for_academic_year(sid, start_year)

        for idx, (mlabel, yr, mo) in enumerate(spec):
            cell = ctk.CTkFrame(grid_frame, corner_radius=12)
            row = 0 if idx < 6 else 1
            col = idx if idx < 6 else idx - 6
            cell.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            grid_frame.grid_rowconfigure(row, weight=1)
            grid_frame.grid_columnconfigure(col, weight=1)

            ctk.CTkLabel(cell, text=mlabel, font=("", 12, "bold")).pack(anchor="w", padx=8, pady=(6, 2))

            # Determine editability vs join date
            editable = True
            if join_dt:
                anchor = date(yr, mo, 1)
                if anchor < date(join_dt.year, join_dt.month, 1):
                    editable = False

            status_var = ctk.StringVar(value="unpaid")
            date_var = ctk.StringVar(value="")
            if (yr, mo) in existing:
                prev_status, prev_date = existing[(yr, mo)]
                status_var.set(prev_status if prev_status in ("paid", "unpaid") else "unpaid")
                date_var.set(prev_date or "")

            rb_frame = ctk.CTkFrame(cell)
            rb_frame.pack(fill="x", padx=8, pady=(0, 4))
            rb_paid  = ctk.CTkRadioButton(rb_frame, text="Paid",   value="paid",   variable=status_var)
            rb_unpd  = ctk.CTkRadioButton(rb_frame, text="Unpaid", value="unpaid", variable=status_var)
            rb_paid.pack(side="left", padx=(0, 8))
            rb_unpd.pack(side="left")

            entry = ctk.CTkEntry(cell, textvariable=date_var, placeholder_text="YYYY-MM-DD")
            entry.pack(fill="x", padx=8, pady=(0, 8))

            # Auto-date on Paid; clear on Unpaid
            def on_status_change(var=status_var, dvar=date_var):
                if var.get() == "paid":
                    if not dvar.get():
                        dvar.set(date.today().isoformat())
                else:
                    dvar.set("")
            status_var.trace_add("write", lambda *_a, f=on_status_change: f())

            if not editable:
                rb_paid.configure(state="disabled")
                rb_unpd.configure(state="disabled")
                entry.configure(state="disabled")
                ctk.CTkLabel(cell, text="No record (before join)", font=("", 11)).pack(anchor="w", padx=8, pady=(0, 6))

            month_cells.append({
                "year": yr,
                "month": mo,
                "label": mlabel,
                "enabled": editable,
                "status_var": status_var,
                "date_var": date_var,
            })

    build_grid()
    year_menu.configure(command=lambda _choice: build_grid())

    # --- Action buttons
    btn_frame = ctk.CTkFrame(win)
    btn_frame.pack(fill="x", padx=12, pady=(0, 12))
    btn_frame.grid_columnconfigure(0, weight=1)

    def on_cancel():
        win.destroy()

    def on_save():
        items = []
        invalid = []
        for cell in month_cells:
            if not cell["enabled"]:
                continue
            paid = cell["status_var"].get()
            pdate = cell["date_var"].get().strip()
            if paid == "paid":
                if not validate_date_string(pdate):
                    invalid.append(cell["label"])
                items.append({
                    "year": cell["year"],
                    "month": cell["month"],
                    "paid": "paid",
                    "payment_date": pdate
                })
            else:
                items.append({
                    "year": cell["year"],
                    "month": cell["month"],
                    "paid": "unpaid",
                    "payment_date": ""  # NOT NULL column; empty string is allowed
                })

        if invalid:
            messagebox.showerror("Invalid dates", "Fix these month(s):\n" + "\n".join(invalid) + "\n\nUse YYYY-MM-DD.")
            return

        try:
            upsert_payments_bulk(sid, items)
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to save payments.\n{e}")
            return

        try:
            if on_saved:
                on_saved(sid)
            else:
                refresh_views_after_payment_update(sid)  # currently no-op
        except Exception:
            pass

        messagebox.showinfo("Saved", "Payments updated successfully.")
        win.destroy()

    ctk.CTkButton(btn_frame, text="Cancel", fg_color="#8E8E93", hover_color="#7A7A7E", command=on_cancel).pack(side="right", padx=(0, 8))
    ctk.CTkButton(btn_frame, text="Save",   fg_color="#43C24E", command=on_save).pack(side="right")
# --- Compatibility stubs for refresh functions ---
def refresh_payment_history_popup(student_id: int):
    """Stub: refresh history popup if open, else just refresh main tree."""
    try:
        refresh_treeview_all()
    except Exception:
        pass

def reload_current_view():
    """Stub: refresh current main view (fallback)."""
    try:
        refresh_treeview_all()
    except Exception:
        pass



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
    command=open_full_window
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