import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

import sqlite3
import os
import time
import json
import textwrap

from datetime import datetime, date
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


def open_full_window():
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

def open_edit_payment_modal(student_id: int, on_saved=None):
    """
    Edit Payment modal for one student.
    - Read-only: ID, Name, Groups, Join Date
    - AY selector (defaults to current AY)
    - 12 month grid (Aug..Jul): Paid/Unpaid radios + date entry
    - Months before join date are disabled ("No record (before join)")
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
