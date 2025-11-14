import customtkinter as ctk
import tkinter as tk
import shutil
import os
import time
import webbrowser
import urllib.parse
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from tkinter import filedialog, simpledialog, messagebox

from DB import (
    DBError,
    NotFoundError,
    get_all_students,
    get_all_groups as db_get_all_groups,
    get_student,
    get_student_groups,
    set_student_groups,
    get_group_students,
    get_groupless_students,
    delete_students_by_ids,
    get_unpaid_students_for_month,
    get_student_counts_by_group,
    get_payments_for_student_academic_year,
    upsert_payments_bulk,
)

# These will be injected from the main file:
#   menu_tools.ElNajahSchool = ElNajahSchool
#   menu_tools.refresh_treeview_all = refresh_treeview_all
#   menu_tools.get_all_groups = get_all_groups  (optional)
ElNajahSchool = None
refresh_treeview_all = None
get_all_groups = db_get_all_groups  # fallback to DB version


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _root():
    """Return the main window or None."""
    return ElNajahSchool


def _today_str():
    from datetime import date
    return date.today().strftime("%Y-%m-%d")


def _ensure_groups_func():
    global get_all_groups
    if get_all_groups is None:
        get_all_groups = db_get_all_groups


# ---------------------------------------------------------------------------
# Tools: delete groupless students
# ---------------------------------------------------------------------------

def delete_groupless_students():
    """
    Delete all students that are not in any group.

    Uses DB.get_groupless_students() + DB.delete_students_by_ids().
    """
    try:
        groupless = get_groupless_students()
    except DBError as e:
        messagebox.showerror("DB Error", f"Could not find groupless students:\n{e}")
        return

    if not groupless:
        messagebox.showinfo("No Groupless Students", "No students without groups were found.")
        return

    names_list = "\n".join(f"- {s['id']} · {s['name']}" for s in groupless[:10])
    extra = ""
    if len(groupless) > 10:
        extra = f"\n… and {len(groupless) - 10} more."

    if not messagebox.askyesno(
        "Confirm Delete",
        f"The following students have NO groups:\n\n{names_list}{extra}\n\n"
        f"Delete ALL of them? This cannot be undone (except via a full DB restore).",
    ):
        return

    ids = [s["id"] for s in groupless]
    try:
        delete_students_by_ids(ids)
    except DBError as e:
        messagebox.showerror("DB Error", f"Error deleting students:\n{e}")
        return

    messagebox.showinfo("Deleted", f"Deleted {len(ids)} groupless students.")
    if refresh_treeview_all:
        refresh_treeview_all()


# ---------------------------------------------------------------------------
# Tools: merge duplicate students (same name)
# ---------------------------------------------------------------------------

def merge_duplicate_students():
    """
    Automatically merge students with the SAME name (case-insensitive).

    Strategy:
        - For each name, keep the student with the lowest ID as the master.
        - Merge groups and payments of other students with same name into master.
        - Delete the duplicates.

    NOTE: This uses a simple rule; it will not ask which one to keep.
    """
    try:
        students = get_all_students(order_by="name")
    except DBError as e:
        messagebox.showerror("DB Error", f"Could not load students:\n{e}")
        return

    # Group students by lowercased name
    by_name = {}
    for stu in students:
        key = stu.name.strip().lower()
        by_name.setdefault(key, []).append(stu)

    # Collect all duplicate clusters
    clusters = [lst for lst in by_name.values() if len(lst) > 1]
    if not clusters:
        messagebox.showinfo("No Duplicates", "No duplicate names found to merge.")
        return

    count_students = sum(len(c) for c in clusters)
    if not messagebox.askyesno(
        "Merge Duplicates",
        "This will automatically merge students with the same name.\n\n"
        "For each name, the student with the lowest ID will be kept, and the others "
        "will be merged into it (groups + payments) and then deleted.\n\n"
        f"Number of duplicate clusters: {len(clusters)}\n"
        f"Total students in those clusters: {count_students}\n\n"
        "Do you want to continue?"
    ):
        return

    from DB import get_payments_for_student, get_payment, upsert_payment  # to avoid huge imports at top

    merged_pairs = []  # list of (master_id, removed_id)

    for cluster in clusters:
        # Sort by id, keep the one with smallest id as master
        cluster_sorted = sorted(cluster, key=lambda s: s.id)
        master = cluster_sorted[0]
        others = cluster_sorted[1:]

        # Collect master groups / payments
        try:
            master_groups = set(get_student_groups(master.id))
        except DBError:
            master_groups = set()

        try:
            master_payments = get_payments_for_student(master.id)
        except DBError:
            master_payments = []
        master_map = {(p.year, p.month): p for p in master_payments}

        # For each duplicate student
        for dup in others:
            try:
                dup_groups = set(get_student_groups(dup.id))
            except DBError:
                dup_groups = set()

            try:
                dup_payments = get_payments_for_student(dup.id)
            except DBError:
                dup_payments = []

            # Merge groups
            combined_groups = master_groups.union(dup_groups)
            try:
                set_student_groups(master.id, sorted(combined_groups))
            except DBError:
                pass
            master_groups = combined_groups

            # Merge payments:
            #   - If master has no record for (year,month), copy dup's record.
            #   - If both have records:
            #       * if one is 'paid' and the other is 'unpaid', choose 'paid'.
            #       * if both 'paid', choose the one with earlier payment_date.
            merge_items = []
            for p in dup_payments:
                mk = (p.year, p.month)
                mp = master_map.get(mk)
                if mp is None:
                    # master has nothing -> copy dup
                    merge_items.append({
                        "year": p.year,
                        "month": p.month,
                        "paid": p.paid,
                        "payment_date": p.payment_date,
                    })
                else:
                    # conflict
                    chosen_paid = mp.paid
                    chosen_date = mp.payment_date

                    if mp.paid == "paid" and p.paid == "unpaid":
                        pass  # keep master
                    elif mp.paid == "unpaid" and p.paid == "paid":
                        chosen_paid = "paid"
                        chosen_date = p.payment_date
                    elif mp.paid == "paid" and p.paid == "paid":
                        # keep the earlier date
                        if p.payment_date < mp.payment_date:
                            chosen_date = p.payment_date

                    merge_items.append({
                        "year": p.year,
                        "month": p.month,
                        "paid": chosen_paid,
                        "payment_date": chosen_date,
                    })

            if merge_items:
                try:
                    upsert_payments_bulk(master.id, merge_items)
                except DBError:
                    pass

            # Delete duplicate student
            try:
                delete_students_by_ids([dup.id])
            except DBError:
                continue

            merged_pairs.append((master.id, dup.id))

    if not merged_pairs:
        messagebox.showinfo("No Changes", "No students were merged.")
    else:
        msg = (
            f"Merged {len(merged_pairs)} students into their master records.\n"
            "Lowest IDs were kept as masters."
        )
        messagebox.showinfo("Merge Complete", msg)
        if refresh_treeview_all:
            refresh_treeview_all()


# ---------------------------------------------------------------------------
# Tools: bulk remove group if only group
# ---------------------------------------------------------------------------

def bulk_remove_group_if_only_group():
    """
    Remove a chosen group from any student for whom it is their ONLY group.

    Example:
        - If student is only in 'Group A', and you choose 'Group A', they become groupless.
        - If student is in 'Group A, Group B', they are not modified.
    """
    _ensure_groups_func()
    root = _root() or ctk.CTk()

    groups = get_all_groups()
    if not groups:
        messagebox.showinfo("No Groups", "There are no groups defined.")
        if root is not ElNajahSchool:
            root.destroy()
        return

    dlg = ctk.CTkToplevel(root)
    dlg.title("Bulk Remove Group (Only Group)")
    dlg.geometry("360x200")
    dlg.grab_set()
    dlg.focus_force()

    ctk.CTkLabel(dlg, text="Choose group to remove\n(only when it is the only group):",
                 font=("Arial", 14), justify="center").pack(pady=(16, 8))

    group_var = ctk.StringVar(value=groups[0])
    option = ctk.CTkOptionMenu(dlg, variable=group_var, values=groups, width=200)
    option.pack(pady=4)

    btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_frame.pack(pady=12)

    def handle_ok():
        group_name = group_var.get()
        if not group_name:
            dlg.destroy()
            return

        if not messagebox.askyesno(
            "Confirm",
            f"Remove group '{group_name}' from any student for whom it is their ONLY group?\n"
            f"Students who belong to multiple groups will not be changed."
        ):
            return

        try:
            students = get_group_students(group_name)
        except DBError as e:
            messagebox.showerror("DB Error", str(e))
            dlg.destroy()
            return

        changed = 0
        for stu in students:
            try:
                groups_for_stu = get_student_groups(stu.id)
            except DBError:
                continue
            if len(groups_for_stu) == 1 and groups_for_stu[0] == group_name:
                try:
                    set_student_groups(stu.id, [])
                except DBError:
                    continue
                changed += 1

        messagebox.showinfo(
            "Done",
            f"Removed group '{group_name}' from {changed} student(s) where it was the only group."
        )
        dlg.destroy()
        if refresh_treeview_all:
            refresh_treeview_all()

    ctk.CTkButton(btn_frame, text="Apply", command=handle_ok, fg_color="#3B82F6").pack(side="left", padx=4)
    ctk.CTkButton(btn_frame, text="Cancel", command=dlg.destroy).pack(side="left", padx=4)


# ---------------------------------------------------------------------------
# Backup / Restore / Purge
# ---------------------------------------------------------------------------

def _db_path():
    # your DB file name; keep in sync with DB.py
    return "elnajah.db"


def backup_database():
    """
    Create a timestamped backup of elnajah.db in a 'backups' folder.
    """
    db_file = _db_path()
    if not os.path.exists(db_file):
        messagebox.showerror("Error", f"Database file not found:\n{db_file}")
        return

    os.makedirs("backups", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"elnajah_backup_{timestamp}.db"
    dest = os.path.join("backups", backup_name)

    try:
        shutil.copy2(db_file, dest)
    except Exception as e:
        messagebox.showerror("Backup Error", f"Could not back up database:\n{e}")
        return

    messagebox.showinfo("Backup Complete", f"Database backed up to:\n{dest}")


def restore_backup():
    """
    Restore a backup into elnajah.db.

    WARNING: This overwrites the current DB; user will be prompted.
    """
    root = _root()
    initial_dir = os.path.abspath("backups") if os.path.isdir("backups") else os.getcwd()

    filename = filedialog.askopenfilename(
        parent=root,
        title="Select Backup File",
        initialdir=initial_dir,
        filetypes=[("DB Files", "*.db"), ("All Files", "*.*")],
    )
    if not filename:
        return

    if not messagebox.askyesno(
        "Confirm Restore",
        "Restoring this backup will overwrite the current database file.\n\n"
        f"Backup: {filename}\n\n"
        "You should close and restart the application after restoring.\n"
        "Continue?"
    ):
        return

    db_file = _db_path()
    try:
        shutil.copy2(filename, db_file)
    except Exception as e:
        messagebox.showerror("Restore Error", f"Could not restore backup:\n{e}")
        return

    messagebox.showinfo(
        "Restore Complete",
        "Backup restored successfully.\n\n"
        "Please CLOSE and RESTART the application now."
    )


def purge_old_backups():
    """
    Delete old backup files, keeping only the N most recent in 'backups'.
    """
    if not os.path.isdir("backups"):
        messagebox.showinfo("No Backups", "The 'backups' folder does not exist.")
        return

    keep_str = simpledialog.askstring(
        "Purge Backups",
        "Keep how many most recent backups? (default: 5)",
        parent=_root(),
    )
    if keep_str is None:
        return

    keep_str = keep_str.strip()
    if not keep_str:
        keep_n = 5
    else:
        try:
            keep_n = max(1, int(keep_str))
        except ValueError:
            messagebox.showerror("Invalid Number", "Please enter a valid integer.")
            return

    backups = []
    for fname in os.listdir("backups"):
        path = os.path.join("backups", fname)
        if os.path.isfile(path):
            backups.append((path, os.path.getmtime(path)))

    if len(backups) <= keep_n:
        messagebox.showinfo("No Purge Needed", "There are not enough backups to purge.")
        return

    backups.sort(key=lambda x: x[1], reverse=True)
    to_keep = backups[:keep_n]
    to_delete = backups[keep_n:]

    for path, _ in to_delete:
        try:
            os.remove(path)
        except Exception:
            continue

    messagebox.showinfo(
        "Purge Complete",
        f"Kept {len(to_keep)} backups.\nDeleted {len(to_delete)} old backup(s)."
    )


# ---------------------------------------------------------------------------
# Export: group to PDF
# ---------------------------------------------------------------------------

def _ask_group(parent=None) -> str | None:
    """
    Small helper to ask for a group name via CTk popup.
    """
    _ensure_groups_func()
    groups = get_all_groups()
    if not groups:
        messagebox.showinfo("No Groups", "There are no groups defined.")
        return None

    win = ctk.CTkToplevel(parent or _root())
    win.title("Select Group")
    win.geometry("360x200")
    win.grab_set()
    win.focus_force()

    ctk.CTkLabel(win, text="Select Group", font=("Arial", 16, "bold")).pack(pady=(16, 4))
    group_var = ctk.StringVar(value=groups[0])

    menu = ctk.CTkOptionMenu(win, variable=group_var, values=groups, width=220)
    menu.pack(pady=6)

    chosen = {"value": None}

    def on_ok():
        chosen["value"] = group_var.get()
        win.destroy()

    def on_cancel():
        chosen["value"] = None
        win.destroy()

    btn_frame = ctk.CTkFrame(win, fg_color="transparent")
    btn_frame.pack(pady=12)
    ctk.CTkButton(btn_frame, text="OK", command=on_ok, fg_color="#3B82F6").pack(side="left", padx=4)
    ctk.CTkButton(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=4)

    win.wait_window()
    return chosen["value"]


def open_group_selector_and_export():
    """
    Ask user for a group, then export its student list to PDF.
    """
    group_name = _ask_group()
    if not group_name:
        return
    _export_group_to_pdf(group_name)


def _export_group_to_pdf(group_name: str):
    """
    Export the given group's students to a simple portrait A4 PDF.
    """
    try:
        students = get_group_students(group_name)
    except DBError as e:
        messagebox.showerror("DB Error", f"Could not load students for group '{group_name}':\n{e}")
        return

    if not students:
        messagebox.showinfo("No Students", f"No students found in group '{group_name}'.")
        return

    os.makedirs("exports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join("exports", f"group_{group_name.replace(' ', '_')}_{timestamp}.pdf")

    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    left = 40
    y = height - 40

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, "El Najah School")
    y -= 20
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, f"Group: {group_name}")
    y -= 25

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(left, y, "ID")
    pdf.drawString(left + 60, y, "Name")
    pdf.drawString(left + 260, y, "Join Date")
    y -= 16

    pdf.setFont("Helvetica", 9)
    for stu in students:
        if y < 50:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 9)

        pdf.drawString(left, y, str(stu.id))
        pdf.drawString(left + 60, y, stu.name[:30])
        pdf.drawString(left + 260, y, stu.join_date)
        y -= 14

    pdf.save()
    messagebox.showinfo("Export Complete", f"Group list saved to:\n{filename}")


# ---------------------------------------------------------------------------
# Export: all students to Excel
# ---------------------------------------------------------------------------

def export_all_students_excel():
    """
    Export all students (ID, Name, Join Date, Groups) to an Excel file.
    """
    try:
        students = get_all_students(order_by="name")
    except DBError as e:
        messagebox.showerror("DB Error", f"Could not load students:\n{e}")
        return

    if not students:
        messagebox.showinfo("No Data", "No students to export.")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Students"

    ws.append(["ID", "Name", "Join Date", "Groups"])

    for stu in students:
        try:
            groups_list = get_student_groups(stu.id)
        except DBError:
            groups_list = []
        groups_str = ", ".join(groups_list)
        ws.append([stu.id, stu.name, stu.join_date, groups_str])

    os.makedirs("exports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join("exports", f"students_{timestamp}.xlsx")

    try:
        wb.save(filename)
    except Exception as e:
        messagebox.showerror("Export Error", f"Could not save Excel file:\n{e}")
        return

    messagebox.showinfo("Export Complete", f"Excel file saved to:\n{filename}")


# ---------------------------------------------------------------------------
# Export: unpaid students to PDF
# ---------------------------------------------------------------------------

def export_unpaid_students_pdf():
    """
    Ask for Year and Month, then export unpaid students for that period to PDF.
    """
    now = datetime.now()
    year_str = simpledialog.askstring(
        "Year",
        f"Enter year (YYYY):",
        initialvalue=str(now.year),
        parent=_root(),
    )
    if year_str is None:
        return
    try:
        year = int(year_str)
    except ValueError:
        messagebox.showerror("Invalid Year", "Please enter a valid year (e.g. 2024).")
        return

    month_str = simpledialog.askstring(
        "Month",
        "Enter month number (1–12):",
        initialvalue=str(now.month),
        parent=_root(),
    )
    if month_str is None:
        return
    try:
        month = int(month_str)
        if not (1 <= month <= 12):
            raise ValueError
    except ValueError:
        messagebox.showerror("Invalid Month", "Please enter a valid month number (1–12).")
        return

    try:
        rows = get_unpaid_students_for_month(year, month, group_name=None)
    except DBError as e:
        messagebox.showerror("DB Error", f"Could not load unpaid students:\n{e}")
        return

    if not rows:
        messagebox.showinfo("No Data", "No unpaid students found for that period.")
        return

    os.makedirs("exports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join("exports", f"unpaid_{year}_{month:02d}_{timestamp}.pdf")

    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    left = 40
    y = height - 40

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, "El Najah School")
    y -= 20
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, f"Unpaid Students — {year}-{month:02d}")
    y -= 25

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(left, y, "ID")
    pdf.drawString(left + 60, y, "Name")
    pdf.drawString(left + 260, y, "Groups")
    y -= 16

    pdf.setFont("Helvetica", 9)
    for row in rows:
        if y < 50:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 9)

        pdf.drawString(left, y, str(row["id"]))
        pdf.drawString(left + 60, y, row["name"][:28])
        pdf.drawString(left + 260, y, row["groups"][:40])
        y -= 14

    pdf.save()
    messagebox.showinfo("Export Complete", f"Unpaid students report saved to:\n{filename}")


# ---------------------------------------------------------------------------
# Export: student count by group to PDF
# ---------------------------------------------------------------------------

def export_student_count_pdf():
    """
    Export total number of students per group (plus overall total) to PDF.
    """
    try:
        counts = get_student_counts_by_group()
    except DBError as e:
        messagebox.showerror("DB Error", f"Could not load group counts:\n{e}")
        return

    if not counts:
        messagebox.showinfo("No Data", "No group data to export.")
        return

    os.makedirs("exports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join("exports", f"student_counts_{timestamp}.pdf")

    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    left = 40
    y = height - 40

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, "El Najah School")
    y -= 20
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, "Student Count by Group")
    y -= 25

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(left, y, "Group")
    pdf.drawString(left + 260, y, "Count")
    y -= 16

    pdf.setFont("Helvetica", 9)
    for row in counts:
        if y < 50:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 9)
        pdf.drawString(left, y, str(row["group"]))
        pdf.drawString(left + 260, y, str(row["count"]))
        y -= 14

    pdf.save()
    messagebox.showinfo("Export Complete", f"Student count report saved to:\n{filename}")


# ---------------------------------------------------------------------------
# Export: single student's payment history (academic year) to PDF
# ---------------------------------------------------------------------------

def _months_for_academic_year(start_year: int):
    """
    Same logic as in paymants_log: returns list of (year, month, label).
    Academic year: Aug(start_year)..Dec(start_year), Jan(start_year+1)..Jul(start_year+1).
    """
    labels = ["Aug", "Sep", "Oct", "Nov", "Dec",
              "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"]
    months = []
    for idx, lab in enumerate(labels):
        if idx < 5:
            y = start_year
            m = 8 + idx
        else:
            y = start_year + 1
            m = idx - 4
        months.append((y, m, lab))
    return months


def export_student_payment_history_pdf():
    """
    Prompt for Student ID and academic start year (e.g. 2024 for 2024–2025),
    then export Aug(start_year)..Jul(start_year+1) payments to a PDF.
    """
    root = _root()

    sid_str = simpledialog.askstring(
        "Student ID",
        "Enter Student ID (number):",
        parent=root,
    )
    if sid_str is None:
        return
    try:
        student_id = int(sid_str)
    except ValueError:
        messagebox.showerror("Invalid ID", "Student ID must be a number.")
        return

    start_year_str = simpledialog.askstring(
        "Academic Year Start",
        "Enter academic year start (e.g. 2024 for 2024–2025):",
        parent=root,
    )
    if start_year_str is None:
        return
    try:
        start_year = int(start_year_str)
    except ValueError:
        messagebox.showerror("Invalid Year", "Please enter a valid year.")
        return

    try:
        stu = get_student(student_id)
        groups_list = get_student_groups(student_id)
        payments = get_payments_for_student_academic_year(student_id, start_year)
    except NotFoundError:
        messagebox.showerror("Not Found", f"Student {student_id} not found.")
        return
    except DBError as e:
        messagebox.showerror("DB Error", str(e))
        return

    pay_map = {(p.year, p.month): p for p in payments}
    months_spec = _months_for_academic_year(start_year)
    groups_str = ", ".join(groups_list)

    os.makedirs("exports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(
        "exports",
        f"student_{student_id}_payments_{start_year}_{start_year+1}_{timestamp}.pdf"
    )

    pdf = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    left = 40
    y = height - 40

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, "El Najah School")
    y -= 20
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, f"Student Payment History — {student_id}: {stu.name}")
    y -= 16
    pdf.setFont("Helvetica", 10)
    pdf.drawString(left, y, f"Groups: {groups_str or 'None'}")
    y -= 14
    pdf.drawString(left, y, f"Academic Year: {start_year}-{start_year+1}")
    y -= 20

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(left, y, "Month")
    pdf.drawString(left + 120, y, "Status")
    pdf.drawString(left + 260, y, "Payment Date")
    y -= 16

    pdf.setFont("Helvetica", 9)
    for (py, pm, label) in months_spec:
        if y < 50:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 9)

        p = pay_map.get((py, pm))
        if p:
            status = "Paid" if p.paid == "paid" else "Unpaid"
            date_str = p.payment_date
        else:
            status = ""
            date_str = ""

        month_str = f"{label} {py}-{pm:02d}"
        pdf.drawString(left, y, month_str)
        pdf.drawString(left + 120, y, status)
        pdf.drawString(left + 260, y, date_str)
        y -= 14

    pdf.save()
    messagebox.showinfo("Export Complete", f"Student payment history saved to:\n{filename}")


# ---------------------------------------------------------------------------
# Help menu
# ---------------------------------------------------------------------------

def contact_support():
    """
    Open default mail client to contact support.
    """
    to_address = "support@example.com"  # change to your real support email
    subject = "El Najah School - Support"
    body = "Hello,\n\nI need help with El Najah School Manager.\n\nThanks."
    url = f"mailto:{to_address}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    webbrowser.open(url)


def send_feedback():
    """
    Open default mail client to send feedback.
    """
    to_address = "feedback@example.com"  # change to your real feedback email
    subject = "El Najah School - Feedback"
    body = "Hello,\n\nHere is my feedback about El Najah School Manager:\n\n"
    url = f"mailto:{to_address}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    webbrowser.open(url)
