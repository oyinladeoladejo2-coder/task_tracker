import customtkinter as ctk
import json
import os
from datetime import datetime

FILE_NAME = "task.json"
current_filter = "all"
editing_id = None  # set when you click Edit on a task

STATUS_COLORS = {
    "todo": "#6b7280",
    "in-progress": "#f59e0b",
    "done": "#22c55e",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def load_tasks():
    if not os.path.exists(FILE_NAME):
        with open(FILE_NAME, "w") as file:
            json.dump([], file)
    with open(FILE_NAME, "r") as file:
        return json.load(file)


def save_tasks(tasks):
    with open(FILE_NAME, "w") as file:
        json.dump(tasks, file, indent=4)


def refresh_list():
    # remove old task cards, then rebuild from the file
    for widget in list_frame.winfo_children():
        widget.destroy()

    shown = 0
    for task in load_tasks():
        if current_filter != "all" and task["status"] != current_filter:
            continue
        shown += 1
        build_task_row(task)

    if shown == 0:
        ctk.CTkLabel(list_frame, text="No tasks to show.").pack(pady=20)


def build_task_row(task):
    row = ctk.CTkFrame(list_frame)
    row.pack(fill="x", pady=4, padx=4)

    ctk.CTkLabel(
        row, text=task["status"], width=90, corner_radius=8,
        fg_color=STATUS_COLORS.get(task["status"], "gray"), text_color="white",
    ).pack(side="left", padx=8, pady=8)

    ctk.CTkLabel(
        row, text=f"{task['id']}. {task['description']}", anchor="w"
    ).pack(side="left", fill="x", expand=True)

    # right-side buttons (first packed = rightmost)
    ctk.CTkButton(
        row, text="Delete", width=60, fg_color="#dc2626", hover_color="#b91c1c",
        command=lambda: delete_task(task["id"]),
    ).pack(side="right", padx=4)
    ctk.CTkButton(
        row, text="Edit", width=60, command=lambda: start_edit(task)
    ).pack(side="right", padx=4)
    ctk.CTkButton(
        row, text="Done", width=60, command=lambda: set_status(task["id"], "done")
    ).pack(side="right", padx=4)
    ctk.CTkButton(
        row, text="Start", width=60,
        command=lambda: set_status(task["id"], "in-progress"),
    ).pack(side="right", padx=4)


def on_filter_change(value):
    global current_filter
    current_filter = value.lower()  # "All" -> "all", "In-Progress" -> "in-progress"
    refresh_list()


def add_or_update():
    global editing_id
    description = entry.get().strip()
    if not description:
        return

    tasks = load_tasks()
    now = datetime.now().isoformat()

    if editing_id is None:
        new_id = 1 if not tasks else max(task["id"] for task in tasks) + 1
        tasks.append({
            "id": new_id,
            "description": description,
            "status": "todo",
            "createdAt": now,
            "updatedAt": now,
        })
    else:
        for task in tasks:
            if task["id"] == editing_id:
                task["description"] = description
                task["updatedAt"] = now
                break
        editing_id = None
        add_button.configure(text="Add Task")

    save_tasks(tasks)
    entry.delete(0, "end")
    refresh_list()


def start_edit(task):
    global editing_id
    editing_id = task["id"]
    entry.delete(0, "end")
    entry.insert(0, task["description"])
    add_button.configure(text="Save Changes")
    entry.focus()


def set_status(task_id, new_status):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = new_status
            task["updatedAt"] = datetime.now().isoformat()
            break
    save_tasks(tasks)
    refresh_list()


def delete_task(task_id):
    global editing_id
    editing_id = None                      # cancel any edit in progress,
    add_button.configure(text="Add Task")  # because the IDs are about to shift

    tasks = [task for task in load_tasks() if task["id"] != task_id]

    # renumber so the IDs stay 1, 2, 3...
    for position, task in enumerate(tasks, start=1):
        task["id"] = position

    save_tasks(tasks)
    refresh_list()

# ---------- window ----------

app = ctk.CTk()
app.title("Task Tracker")
app.geometry("800x600")

ctk.CTkLabel(
    app, text="Task Tracker", font=ctk.CTkFont(size=28, weight="bold")
).pack(pady=(20, 10))

filter_bar = ctk.CTkSegmentedButton(
    app, values=["All", "Todo", "In-Progress", "Done"], command=on_filter_change
)
filter_bar.set("All")
filter_bar.pack(pady=5)

# bottom input bar (packed before the list so the list fills the rest)
input_frame = ctk.CTkFrame(app)
input_frame.pack(side="bottom", fill="x", padx=20, pady=15)

entry = ctk.CTkEntry(input_frame, placeholder_text="Type a task...")
entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
entry.bind("<Return>", lambda event: add_or_update())

add_button = ctk.CTkButton(input_frame, text="Add Task", command=add_or_update)
add_button.pack(side="right", padx=10)

list_frame = ctk.CTkScrollableFrame(app)
list_frame.pack(fill="both", expand=True, padx=20, pady=10)

refresh_list()
app.mainloop()  # always the last line
