import customtkinter as ctk
import io
import json
import os
import re
import threading
import wave
from datetime import datetime, timedelta
from tkinter import messagebox, filedialog

try:
    import winsound  # built into Python on Windows
except ImportError:
    winsound = None

FILE_NAME = "task.json"

# ---- ALARM SETTINGS: change these inside the app (Alarm Settings button) ----
# They are saved in settings.json, next to this script.
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
DEFAULT_SETTINGS = {"alarm_style": "melody", "alarm_file": "alarm.wav"}
settings = dict(DEFAULT_SETTINGS)

STYLE_LABELS = {  # setting value -> name shown in the app
    "melody": "Rising chime",
    "classic": "Classic alarm clock",
    "siren": "Siren",
    "urgent": "Urgent beeps",
    "wav": "My own sound file",
}

ALARM_PATTERNS = {  # (pitch in Hz, length in milliseconds)
    "melody": [(523, 250), (659, 250), (784, 250), (1047, 450), (784, 250), (659, 250)],
    "classic": [(1000, 150), (1000, 150), (1000, 150), (1000, 150)],
    "siren": [(f, 40) for f in range(600, 1300, 50)] + [(f, 40) for f in range(1250, 550, -50)],
    "urgent": [(1800, 100), (900, 100)] * 6,
}

current_filter = "all"
editing_id = None  # set when you click Edit on a task
timer_labels = {}  # task_id -> (label widget, end time) for every running timer

# alarm state
alarm_stop = threading.Event()
alarm_on = False
alarm_popup = None
settings_window = None

STATUS_COLORS = {
    "todo": "#6b7280",
    "in-progress": "#f59e0b",
    "done": "#22c55e",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ---------- saving and loading ----------

def save_tasks(tasks):
    with open(FILE_NAME, "w") as file:
        json.dump(tasks, file, indent=4)


def load_tasks():
    if not os.path.exists(FILE_NAME):
        with open(FILE_NAME, "w") as file:
            json.dump([], file)
    with open(FILE_NAME, "r") as file:
        tasks = json.load(file)

    # keep IDs as 1, 2, 3 with no gaps
    changed = False
    for position, task in enumerate(tasks, start=1):
        if task.get("id") != position:
            task["id"] = position
            changed = True
    if changed:
        save_tasks(tasks)
    return tasks


# ---------- alarm settings (saved between runs) ----------

def load_settings():
    try:
        with open(SETTINGS_PATH, "r") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return  # no settings yet, or a broken file: keep the defaults
    if not isinstance(data, dict):
        return
    if data.get("alarm_style") in STYLE_LABELS:
        settings["alarm_style"] = data["alarm_style"]
    if isinstance(data.get("alarm_file"), str) and data["alarm_file"]:
        settings["alarm_file"] = data["alarm_file"]


def save_settings():
    try:
        with open(SETTINGS_PATH, "w") as file:
            json.dump(settings, file, indent=4)
    except OSError:
        pass  # not being able to save settings should never crash the app


# ---------- date and timer helpers ----------

def format_date(iso_text):
    """Turn '2026-10-31T05:10:22.123456' into 'Oct 31, 2026 05:10 AM'."""
    try:
        return datetime.fromisoformat(iso_text).strftime("%b %d, %Y %I:%M %p")
    except (ValueError, TypeError):
        return "unknown"


def format_remaining(seconds):
    """Turn a number of seconds into '24:59' or '1:05:30'."""
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def timer_text(end_time):
    remaining = (end_time - datetime.now()).total_seconds()
    if remaining <= 0:
        return "Time's up!"
    return f"Time left: {format_remaining(remaining)}   (ends {end_time.strftime('%I:%M %p')})"


def parse_duration(text):
    """Turn '25', '2h', '1h30m', '90s' or '1.5h' into minutes. Returns None if invalid."""
    text = text.strip().lower().replace(" ", "")
    if not text:
        return None

    # a plain number means minutes
    try:
        return float(text)
    except ValueError:
        pass

    match = re.fullmatch(
        r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?", text
    )
    if not match or not any(match.groups()):
        return None

    hours, minutes, seconds = (float(part) if part else 0 for part in match.groups())
    return hours * 60 + minutes + seconds / 60


# ---------- the alarm ----------

sound_lock = threading.Lock()  # makes "start a sound" and "stop it" never overlap
_silence_bytes = None


def make_silence():
    """A tiny silent WAV in memory. Playing it replaces (cuts off) any sound still playing."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(22050)
        out.writeframes(b"\x00\x00" * 1100)  # about 0.05 seconds
    return buffer.getvalue()


def silence_sound():
    """Cut off any .wav that is playing, right now. Tries three different ways."""
    global _silence_bytes
    if not winsound:
        return
    if _silence_bytes is None:
        _silence_bytes = make_silence()
    for stop in (
        lambda: winsound.PlaySound(None, winsound.SND_PURGE),
        lambda: winsound.PlaySound(None, 0),
        lambda: winsound.PlaySound(_silence_bytes, winsound.SND_MEMORY),
    ):
        try:
            stop()
        except Exception:
            pass


def wav_length_seconds(path):
    """How long the sound file lasts, so it can be replayed when it ends."""
    try:
        with wave.open(path, "rb") as sound:
            return sound.getnframes() / float(sound.getframerate())
    except Exception:
        return 5.0


def resolve_sound_path():
    """Full path of the chosen .wav file (a bare name means 'next to this script')."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), settings["alarm_file"])


def alarm_loop(stop_event):
    """Runs in the background: plays the alarm over and over until it is stopped."""
    style = settings["alarm_style"]
    sound_path = resolve_sound_path()

    # option 1: a .wav file, played again and again until you stop the alarm
    # (we replay it ourselves instead of using the Windows "loop" flag,
    #  because a looping sound can refuse to stop on some computers)
    if style == "wav" and winsound and os.path.exists(sound_path):
        gap = wav_length_seconds(sound_path) + 0.4
        while not stop_event.is_set():
            with sound_lock:
                if stop_event.is_set():
                    break
                winsound.PlaySound(
                    sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC
                )
            stop_event.wait(gap)                  # wakes up instantly when stopped
        return

    # option 2: a built-in beep pattern (also used if the .wav file is missing)
    pattern = ALARM_PATTERNS.get(style, ALARM_PATTERNS["melody"])
    while not stop_event.is_set():
        if winsound:
            for frequency, length in pattern:
                if stop_event.is_set():
                    break
                winsound.Beep(frequency, length)
        else:
            print("\a", end="", flush=True)  # fallback on other systems
        stop_event.wait(0.8)


def start_alarm():
    global alarm_on, alarm_stop
    if alarm_on:
        return
    alarm_on = True
    alarm_stop = threading.Event()  # a fresh one each time, so old alarms can't clash
    threading.Thread(target=alarm_loop, args=(alarm_stop,), daemon=True).start()


def stop_alarm():
    global alarm_on, alarm_popup
    alarm_on = False
    with sound_lock:
        alarm_stop.set()
        silence_sound()  # cut off a playing .wav right away
    if alarm_popup is not None:
        try:
            alarm_popup.destroy()
        except Exception:
            pass
        alarm_popup = None


def show_alarm_popup(names):
    """A window that jumps to the front and stays there until you stop the alarm."""
    global alarm_popup

    # if the popup is already open, just add the new task names to it
    if alarm_popup is not None and alarm_popup.winfo_exists():
        for name in names:
            ctk.CTkLabel(alarm_popup, text=f"- {name}", wraplength=340).pack()
        return

    alarm_popup = ctk.CTkToplevel(app)
    alarm_popup.title("Time's up!")
    alarm_popup.geometry("400x260")
    alarm_popup.attributes("-topmost", True)
    alarm_popup.protocol("WM_DELETE_WINDOW", stop_alarm)

    ctk.CTkButton(
        alarm_popup, text="Stop Alarm", height=40,
        fg_color="#dc2626", hover_color="#b91c1c", command=stop_alarm,
    ).pack(side="bottom", pady=20)

    ctk.CTkLabel(
        alarm_popup, text="TIME'S UP!", text_color="#ef4444",
        font=ctk.CTkFont(size=30, weight="bold"),
    ).pack(pady=(20, 10))
    ctk.CTkLabel(alarm_popup, text="The timer has ended for:").pack()
    for name in names:
        ctk.CTkLabel(alarm_popup, text=f"- {name}", wraplength=340).pack()

    # some Windows setups open new windows behind others, so lift it again
    alarm_popup.after(100, alarm_popup.lift)
    alarm_popup.after(150, alarm_popup.focus_force)


def open_settings():
    """The Alarm Settings window: pick a sound, choose your own file, test it."""
    global settings_window
    if settings_window is not None and settings_window.winfo_exists():
        settings_window.lift()
        return

    win = ctk.CTkToplevel(app)
    settings_window = win
    win.title("Alarm Settings")
    win.geometry("440x340")

    test_on = {"value": False}
    label_to_style = {label: style for style, label in STYLE_LABELS.items()}

    def file_text():
        name = os.path.basename(settings["alarm_file"])
        return f"File: {name}" if name else "File: none chosen"

    def stop_test():
        if test_on["value"]:
            test_on["value"] = False
            stop_alarm()
        test_button.configure(text="Test sound")

    def choose_style(label):
        stop_test()
        settings["alarm_style"] = label_to_style[label]
        save_settings()

    def choose_file():
        stop_test()
        path = filedialog.askopenfilename(
            parent=win,
            title="Choose an alarm sound",
            filetypes=[("WAV sound files", "*.wav")],
        )
        if not path:
            return  # cancelled
        settings["alarm_file"] = path
        settings["alarm_style"] = "wav"
        style_menu.set(STYLE_LABELS["wav"])
        file_label.configure(text=file_text())
        save_settings()

    def toggle_test():
        if test_on["value"]:
            stop_test()
            return
        if alarm_on:
            return  # a real alarm is already ringing
        if settings["alarm_style"] == "wav" and not os.path.exists(resolve_sound_path()):
            messagebox.showwarning(
                "Sound file not found",
                "Click 'Choose .wav file...' to pick a sound.\n"
                "Until then, the rising chime plays instead.",
                parent=win,
            )
        test_on["value"] = True
        test_button.configure(text="Stop test")
        start_alarm()

    def close():
        stop_test()
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", close)

    ctk.CTkLabel(
        win, text="Alarm sound", font=ctk.CTkFont(size=20, weight="bold")
    ).pack(pady=(20, 10))

    style_menu = ctk.CTkOptionMenu(
        win, values=list(STYLE_LABELS.values()), command=choose_style, width=240
    )
    style_menu.set(STYLE_LABELS.get(settings["alarm_style"], STYLE_LABELS["melody"]))
    style_menu.pack(pady=5)

    file_label = ctk.CTkLabel(win, text=file_text(), text_color="gray", wraplength=380)
    file_label.pack(pady=(15, 3))
    ctk.CTkButton(
        win, text="Choose .wav file...", width=240, command=choose_file
    ).pack(pady=3)

    test_button = ctk.CTkButton(
        win, text="Test sound", width=240,
        fg_color="#7c3aed", hover_color="#6d28d9", command=toggle_test,
    )
    test_button.pack(pady=(20, 5))

    ctk.CTkButton(
        win, text="Close", width=240, fg_color="#4b5563", hover_color="#374151",
        command=close,
    ).pack(pady=5)

    # some Windows setups open new windows behind others, so lift it
    win.after(100, win.lift)
    win.after(150, win.focus_force)


# ---------- drawing the task list ----------

def refresh_list():
    # remove old task cards, then rebuild from the file
    timer_labels.clear()
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

    # middle section: description, dates, and the timer line
    info = ctk.CTkFrame(row, fg_color="transparent")
    info.pack(side="left", fill="x", expand=True)

    ctk.CTkLabel(
        info, text=f"{task['id']}. {task['description']}", anchor="w"
    ).pack(fill="x")

    dates = f"Created: {format_date(task.get('createdAt'))}"
    if task.get("updatedAt") != task.get("createdAt"):
        dates += f"   |   Updated: {format_date(task.get('updatedAt'))}"

    ctk.CTkLabel(
        info, text=dates, anchor="w", text_color="gray",
        font=ctk.CTkFont(size=11),
    ).pack(fill="x")

    # a running timer, or a timer that already ended
    timer_active = False
    timer_ended = False
    ends_at = task.get("timerEndsAt")
    ended_at = task.get("timerEndedAt")

    if ends_at:
        try:
            end_time = datetime.fromisoformat(ends_at)
            timer_label = ctk.CTkLabel(
                info, text=timer_text(end_time), anchor="w",
                text_color="#a78bfa", font=ctk.CTkFont(size=12, weight="bold"),
            )
            timer_label.pack(fill="x")
            timer_labels[task["id"]] = (timer_label, end_time)
            timer_active = True
        except ValueError:
            pass  # ignore a broken timer value
    elif ended_at:
        timer_ended = True
        row.configure(border_width=2, border_color="#dc2626")  # red outline
        ctk.CTkLabel(
            info, text=f"TIME'S UP!  (timer ended {format_date(ended_at)})",
            anchor="w", text_color="#ef4444",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(fill="x")

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

    if timer_active:
        ctk.CTkButton(
            row, text="Stop Timer", width=80,
            fg_color="#7c3aed", hover_color="#6d28d9",
            command=lambda: stop_timer(task["id"]),
        ).pack(side="right", padx=4)
    elif task["status"] != "done":  # finished tasks don't need a timer
        ctk.CTkButton(
            row, text="New Timer" if timer_ended else "Timer", width=80,
            fg_color="#7c3aed", hover_color="#6d28d9",
            command=lambda: start_timer(task["id"]),
        ).pack(side="right", padx=4)


# ---------- timer logic ----------

def start_timer(task_id):
    dialog = ctk.CTkInputDialog(
        text="How long? Examples: 25 (minutes), 2h, 1h30m, 45s",
        title="Set timer",
    )
    answer = dialog.get_input()
    if answer is None:
        return  # cancelled

    minutes = parse_duration(answer)
    if minutes is None or minutes <= 0:
        messagebox.showwarning(
            "Invalid time",
            "Try something like: 25 (minutes), 2h, 1h30m, or 45s.",
        )
        return

    # store the END time (not a counter) so the timer survives closing the app
    end_time = datetime.now() + timedelta(minutes=minutes)

    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["timerEndsAt"] = end_time.isoformat()
            task.pop("timerEndedAt", None)  # clear the old "time's up" mark
            break
    save_tasks(tasks)
    refresh_list()


def stop_timer(task_id):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task.pop("timerEndsAt", None)
            break
    save_tasks(tasks)
    refresh_list()


def finish_timers(task_ids):
    """Called when one or more timers reach zero. The task status is NOT changed."""
    tasks = load_tasks()
    names = []
    for task in tasks:
        if task["id"] in task_ids:
            names.append(task["description"])
            # remember when it ended, so the card stays marked until you act on it
            task["timerEndedAt"] = task.pop("timerEndsAt", None)
    save_tasks(tasks)
    refresh_list()

    app.deiconify()  # un-minimize the window
    app.lift()
    start_alarm()
    show_alarm_popup(names)


def tick():
    """Runs every second: update each running countdown."""
    app.after(1000, tick)  # schedule the next tick first

    finished = []
    for task_id, (label, end_time) in list(timer_labels.items()):
        if (end_time - datetime.now()).total_seconds() <= 0:
            finished.append(task_id)
        else:
            label.configure(text=timer_text(end_time))

    if finished:
        finish_timers(finished)


# ---------- buttons ----------

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
            if new_status == "done":
                # a finished task needs no timer or "time's up" mark
                task.pop("timerEndsAt", None)
                task.pop("timerEndedAt", None)
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

load_settings()

app = ctk.CTk()
app.title("Task Tracker")
app.geometry("1050x650")

ctk.CTkLabel(
    app, text="Task Tracker", font=ctk.CTkFont(size=28, weight="bold")
).pack(pady=(20, 10))

# top-right corner button that opens the alarm settings
ctk.CTkButton(
    app, text="Alarm Settings", width=120, command=open_settings
).place(relx=1.0, x=-20, y=22, anchor="ne")

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
tick()            # start the once-per-second timer loop
app.mainloop()    # always the last line
