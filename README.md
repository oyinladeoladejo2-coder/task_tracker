# Task Tracker

A task manager built in Python, with two ways to use it:

- **Command line (CLI):** add, update, delete and list tasks from the terminal. Uses only Python's standard library.
- **Desktop app (GUI):** a modern window built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter), with colored status labels, filter tabs, per-task buttons, and a **countdown timer with an alarm**.

Both versions read and write the same `task.json` file, so a task added in one shows up in the other.

![Task Tracker GUI](screenshot.png)<img width="959" height="494" alt="screenshot" src="https://github.com/user-attachments/assets/ce102645-97dd-4176-8225-9677a8631af4" />


## Features

**Both versions**
- Add, update and delete tasks
- Mark a task as `todo`, `in-progress` or `done`
- List all tasks, or filter by status
- Tasks are saved in `task.json` (created automatically if it doesn't exist)
- Task IDs always stay in order (1, 2, 3...) with no gaps, even after deleting a task
- Friendly error messages instead of crashes for bad input

**Desktop app only**
- Colored status labels: gray = todo, orange = in-progress, green = done
- Created and updated dates shown on every task
- Filter tabs: All, Todo, In-Progress, Done
- Edit a task's text in place
- **Countdown timer** on any task, with a live display
- **Alarm** that rings when the timer ends, with a Stop Alarm button
- **Alarm Settings** window: pick a built-in sound or your own `.wav` file, and test it
- Tasks whose timer has ended are marked with a red outline until you act on them

## Requirements

- Python 3.8 or higher
- CLI: nothing to install
- GUI: CustomTkinter

```
pip install customtkinter
```

## Getting started

```
git clone https://github.com/oyinladeoladejo2-coder/task-tracker.git
cd task-tracker
```

## Using the CLI

Run all commands from the project folder.

```
python task_cli.py add "Buy groceries"
python task_cli.py update 1 "Buy groceries and cook dinner"
python task_cli.py delete 1
python task_cli.py mark-in-progress 1
python task_cli.py mark-done 1
python task_cli.py list
python task_cli.py list todo
python task_cli.py list in-progress
python task_cli.py list done
```

## Using the GUI

```
python task_ctk.py
```

- **Add a task:** type in the box at the bottom and click **Add Task** (or press Enter).
- **Start / Done:** mark a task in-progress or done.
- **Edit:** click **Edit**, change the text, then click **Save Changes**.
- **Delete:** removes the task and renumbers the rest.
- **Filter:** use the tabs at the top to show only matching tasks.

### Timer and alarm

1. Click **Timer** on a task and type how long you want. Examples:

| You type | Timer length |
|---|---|
| `25` | 25 minutes |
| `45s` | 45 seconds |
| `2h` | 2 hours |
| `1h30m` | 1 hour 30 minutes |

2. The task shows a live countdown, for example `Time left: 24:59`.
3. When it reaches zero, an alarm rings and a **TIME'S UP!** window comes to the front.
4. Click **Stop Alarm** to silence it. The task keeps its status and stays marked in red, so you can then click **Done**, or start a **New Timer** if you need more time.

The timer saves its end time in `task.json`, so it keeps counting even if you close and reopen the app.

### Changing the alarm sound

Click **Alarm Settings** in the top-right corner of the app. No code changes needed.

| Option | Sound |
|---|---|
| Rising chime | A short rising melody (default) |
| Classic alarm clock | Old-fashioned alarm clock beeps |
| Siren | A sweeping up-and-down siren |
| Urgent beeps | Fast, sharp beeping |
| My own sound file | Any `.wav` file you choose with **Choose .wav file...** |

Use **Test sound** to hear your choice before closing. Your choice is saved in `settings.json` and remembered the next time you open the app.

The alarm uses `winsound`, which is built into Python on Windows. On other systems the app still works, but the alarm falls back to a simple terminal beep.

## Task properties

Each task in `task.json` has:

| Property | Description |
|---|---|
| `id` | The task's number (kept as 1, 2, 3... automatically) |
| `description` | What needs to be done |
| `status` | `todo`, `in-progress`, or `done` |
| `createdAt` | When the task was created |
| `updatedAt` | When the task was last changed |
| `timerEndsAt` | *(GUI, optional)* When a running timer ends |
| `timerEndedAt` | *(GUI, optional)* When a timer finished and the task is marked |

## Project files

| File | Purpose |
|---|---|
| `task_tracker.py` | The command line version |
| `task_ctk.py` | The desktop GUI version, with timer and alarm |
| `alarm.wav` | The default sound file for the "My own sound file" option |
| `task.json` | Where tasks are stored (created on first run, not uploaded to GitHub) |
| `settings.json` | Your alarm choice (created when you change it, not uploaded to GitHub) |

## What I learned

- Reading and writing JSON files with Python's built-in modules
- Handling command line arguments with `sys.argv`
- Handling errors and bad input without crashing
- Building a GUI with buttons, filters and live updates
- Using `after()` for a once-per-second countdown without freezing the window
- Running an alarm in a background thread so the app stays responsive
- Keeping a CLI and a GUI in sync through one shared data file

## Credits

Started from the [Task Tracker](https://roadmap.sh/projects/task-tracker) project on roadmap.sh, then extended with a desktop GUI, a countdown timer and an alarm.
