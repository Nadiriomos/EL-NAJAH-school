import customtkinter as ctk
import tkinter as tk
import sqlite3
import shutil
import os
import time
from datetime import datetime
import webbrowser
import urllib.parse
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from tkinter import filedialog
from tkinter import simpledialog, messagebox


def backup_database():
    # Create a timestamp for unique backup names
    timestamp = datetime.now.strftime("%Y-%m-%d_%H-%M-%S")
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

    now = datetime.now()
    year = now.year
    month = now.month
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