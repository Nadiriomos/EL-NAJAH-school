import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import sqlite3

# === Color Scheme ===
background = "#F4F7FA"
primary    = "#3B82F6"  # Blue-500
secondary  = "#60A5FA"  # Blue-400
text       = "#1F2937"  # Gray-800

# === Main Window Setup ===
ElNajahSchool = tk.Tk()
ElNajahSchool.title("El Najah School")
ElNajahSchool.geometry("1024x768")
ElNajahSchool.attributes('-fullscreen', True)
ElNajahSchool.configure(bg=background)
ElNajahSchool.bind("<Escape>", lambda event: ElNajahSchool.quit())  # Exit on Escape key

# === Menu Bar ===
menubar = tk.Menu(ElNajahSchool)
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="Exit", command=ElNajahSchool.quit)
menubar.add_cascade(label="File", menu=file_menu)
ElNajahSchool.config(menu=menubar)

# === Welcome Label ===
label = tk.Label(
    ElNajahSchool,
    text="Welcome to El Najah School",
    font=("Arial", 24),
    bg=background,
    fg=text
)
label.pack(pady=20)

# === Top Frame for Buttons ===
frame = tk.Frame(ElNajahSchool)
frame.pack(pady=0, padx=20, fill='x')

# Left and Right Containers
left_half = tk.Frame(frame, width=480, height=60, bg=background)
left_half.pack(side='left', fill='y', expand=True)
left_half.pack_propagate(False)

right_half = tk.Frame(frame, width=480, height=60, bg=background)
right_half.pack(side='left', fill='y', expand=True)
right_half.pack_propagate(False)

# === Add Student Popup ===
def open_add_student():
    top = tk.Toplevel(ElNajahSchool)
    top.title("New Student Registration")
    top.geometry("500x300")

    label = tk.Label(top, text="Add new student", font=("Arial", 24))
    label.pack(pady=20)

    frame = tk.Frame(top)
    frame.pack(pady=10, padx=20, fill='x')

    entry = tk.Entry(frame, font=("Arial", 18), justify='right')
    entry.pack(side='left', fill='x', expand=True)

    radio_var = tk.StringVar(value="pay")
    radio1 = tk.Radiobutton(frame, text="paid", variable=radio_var, value="paid")
    radio2 = tk.Radiobutton(frame, text="unpaid", variable=radio_var, value="unpaid")
    radio1.pack(side='left', padx=10, pady=10)
    radio2.pack(side='left', padx=10, pady=10)

# === Add Group Popup ===
def open_add_group():
    top = tk.Toplevel(ElNajahSchool)
    top.title("New Group Registration")
    top.geometry("500x300")

    label = tk.Label(top, text="Add new group", font=("Arial", 24))
    label.pack(pady=20)

    frame = tk.Frame(top)
    frame.pack(pady=10, padx=20, fill='x')

    entry = tk.Entry(frame, font=("Arial", 18), justify='right')
    entry.pack(side='left', fill='x', expand=True)

    button = tk.Button(frame, text="Add Group")
    button.pack(side='right', padx=10)

# === Buttons ===
left_button = tk.Button(left_half, text="Add Student", font=("Arial", 16), command=open_add_student, bg=primary, fg=text)
left_button.place(relx=0.5, rely=0.5, anchor="center")

right_button = tk.Button(right_half, text="Add Group", font=("Arial", 16), command=open_add_group, bg=primary, fg=text)
right_button.place(relx=0.5, rely=0.5, anchor="center")

# === Placeholder Function ===
def add_placeholder(entry, placeholder_text, color="gray"):
    def on_focus_in(event):
        if entry.get() == placeholder_text:
            entry.delete(0, "end")
            entry.config(fg="black")
    def on_focus_out(event):
        if entry.get() == "":
            entry.insert(0, placeholder_text)
            entry.config(fg=color)

    entry.insert(0, placeholder_text)
    entry.config(fg=color)
    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)

# === Search Frame ===
search_frame = tk.Frame(ElNajahSchool)
search_frame.pack(pady=10, fill="x", padx=10)

# --- Search by Name ---
left_frame = tk.Frame(search_frame)
left_frame.pack(side="left", expand=True, fill="x", padx=5)

entry1_var = tk.StringVar()
entry1 = tk.Entry(left_frame, textvariable=entry1_var, font=("Arial", 16), justify="right", bg=secondary, fg=text)
entry1.pack(side="left", expand=True, fill="x")
add_placeholder(entry1, "Search by name")

button1 = tk.Button(left_frame, text="Search", command=lambda: None, font=("Arial", 16), bg=primary, fg=text)
button1.pack(side="left", padx=(5, 0))

# --- Search by ID ---
right_frame = tk.Frame(search_frame)
right_frame.pack(side="left", expand=True, fill="x", padx=5)

entry2_var = tk.StringVar()
entry2 = tk.Entry(right_frame, textvariable=entry2_var, font=("Arial", 16), justify="right", bg=secondary, fg=text)
entry2.pack(side="left", expand=True, fill="x")
add_placeholder(entry2, "Search by ID")

button2 = tk.Button(right_frame, text="Search", command=lambda: None, font=("Arial", 16), bg=primary, fg=text)
button2.pack(side="left", padx=(5, 0))

# === Style Configuration for Treeview ===
style = ttk.Style()
style.theme_use("default")

style.configure("Treeview",
    rowheight=30,
    font=("Arial", 12),
    background="white",
    foreground="black",
    fieldbackground="white",
    bordercolor="#2196f3",
    borderwidth=1
)

style.configure("Treeview.Heading",
    font=("Arial", 12, "bold"),
    background="#e0e0e0",
    bordercolor="#2196f3",
    borderwidth=1
)

style.map("Treeview",
    background=[("selected", "#d0f0ff")],
    foreground=[("selected", "black")]
)

# === Treeview Table ===
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

tree.tag_configure("evenrow", background="#f5faff")  # light blue
tree.tag_configure("oddrow", background="white")

# === Header Click Event ===
def open_top(column_name):
    top = tk.Toplevel(ElNajahSchool)
    top.title(f"{column_name.capitalize()} Options")
    top.geometry("300x150")
    tk.Label(top, text=f"This is the {column_name.capitalize()} options window", font=("Arial", 14)).pack(pady=30)

def on_treeview_click(event):
    region = tree.identify_region(event.x, event.y)
    if region == "heading":
        col = tree.identify_column(event.x)
        col_map = {
            '#1': 'id',
            '#2': 'name',
            '#3': 'group',
            '#4': 'pay'
        }
        col_name = col_map.get(col)
        if col_name:
            open_top(col_name)

tree.bind("<Button-1>", on_treeview_click)

# === Start the Application ===
ElNajahSchool.mainloop()
