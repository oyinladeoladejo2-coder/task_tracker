# task_tracker
a python built cli project that helps to manage task and update the progress of the task right from the terminal
# Task Tracker CLI

A simple command line app for tracking what you need to do, what you're working on, and what you've finished. Tasks are saved in a `task.json` file in the same folder. It uses only Python's standard library, so there's nothing to install.

## Requirements

- Python 3.8 or higher

## Usage

Run all commands from the project folder.

### Add a task
```
python task_tracker.py add "Buy groceries"
```

### Update a task
```
python task_tracker.py update 1 "Buy groceries and cook dinner"
```

### Delete a task
```
python task_tracker.py delete 1
```

### Change a task's status
```
python task_tracker.py mark-in-progress 1
python task_tracker.py mark-done 1
```

### List tasks
```
python task_tracker.py list
python task_tracker.py list todo
python task_tracker.py list in-progress
python task_tracker.py list done
```

## Task properties

Each task in `task.json` has:

| Property | Description |
|---|---|
| `id` | Unique number for the task |
| `description` | What needs to be done |
| `status` | `todo`, `in-progress`, or `done` |
| `createdAt` | When the task was created |
| `updatedAt` | When the task was last changed |

## Error handling

The app shows a clear message instead of crashing when you give it a missing command, a missing description, an invalid ID, or an ID that doesn't exist.
