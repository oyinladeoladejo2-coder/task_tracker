import sys
import json
import os
from datetime import datetime


# load tasks from task.json (creates the file if it doesn't exist)
def load_tasks():
  if not os.path.exists("task.json"):
    with open("task.json", "w") as file:
      json.dump([], file)

  with open("task.json", "r") as file:
    return json.load(file)


# save the list of tasks back into task.json
def save_tasks(tasks):
  with open("task.json", "w") as file:
    json.dump(tasks, file)


if len(sys.argv) < 2:
  print("Error: No command provided.")
  print(
      "Usage: python task_cli.py [add|list|update|delete|mark-in-progress|mark-done]"
  )
  sys.exit()

command = sys.argv[1]

# ---- ADD: create a new task ----
if command == "add":
  if len(sys.argv) < 3:
    print("Error: Please provide a task description.")
    print('Usage: python task_cli.py add "Buy milk"')
    sys.exit()

  description = sys.argv[2]
  tasks = load_tasks()

  new_id = 1 if not tasks else max(task["id"] for task in tasks) + 1

  task = {
      "id": new_id,
      "description": description,
      "status": "todo",
      "createdAt": datetime.now().isoformat(),
      "updatedAt": datetime.now().isoformat(),
  }

  tasks.append(task)
  save_tasks(tasks)
  print(f"Task added successfully (ID: {new_id})")

# ---- LIST: show all tasks, or filter by status ----
elif command == "list":
  tasks = load_tasks()
  if len(sys.argv) > 2:
    target_status = sys.argv[2]
    tasks = [task for task in tasks if task["status"] == target_status]

  if not tasks:
    print("No tasks found.")
  else:
    for task in tasks:
      print(
          f"ID: {task['id']}, Description: {task['description']}, Status:"
          f" {task['status']}, Created At: {task['createdAt']}, Updated At:"
          f" {task['updatedAt']}"
      )

# ---- UPDATE / DELETE / MARK: commands that need a task ID ----
elif command in ["update", "delete", "mark-in-progress", "mark-done"]:
  if len(sys.argv) < 3:
    print(f"Error: Missing task ID for '{command}'.")
    print(f"Usage: python task_cli.py {command} [id]")
    sys.exit()

  # Handle non-integer ID inputs gracefully (e.g., text instead of a number)
  try:
    task_id = int(sys.argv[2])
  except ValueError:
    print("Error: Task ID must be a valid number.")
    sys.exit()

  tasks = load_tasks()
  task_found = False

  if command == "update":
    if len(sys.argv) < 4:
      print("Error: Missing new description for update.")
      print('Usage: python task_cli.py update [id] "New description"')
      sys.exit()

    new_description = sys.argv[3]
    for task in tasks:
      if task["id"] == task_id:
        task["description"] = new_description
        task["updatedAt"] = datetime.now().isoformat()
        task_found = True
        break

    if task_found:
      save_tasks(tasks)
      print(f"Task {task_id} updated successfully.")
    else:
      print(f"Error: Task with ID {task_id} not found.")

  elif command == "delete":
    updated_tasks = [task for task in tasks if task["id"] != task_id]
    if len(updated_tasks) < len(tasks):
      # renumber so the IDs stay 1, 2, 3 with no gaps
      for position, t in enumerate(updated_tasks, start=1):
        t["id"] = position
      save_tasks(updated_tasks)
      print(f"Task {task_id} deleted successfully.")
    else:
      print(f"Error: Task with ID {task_id} not found.")

  elif command == "mark-in-progress":
    for task in tasks:
      if task["id"] == task_id:
        task["status"] = "in-progress"
        task["updatedAt"] = datetime.now().isoformat()
        task_found = True
        break

    if task_found:
      save_tasks(tasks)
      print(f"Task {task_id} marked as in-progress.")
    else:
      print(f"Error: Task with ID {task_id} not found.")

  elif command == "mark-done":
    for task in tasks:
      if task["id"] == task_id:
        task["status"] = "done"
        task["updatedAt"] = datetime.now().isoformat()
        task_found = True
        break

    if task_found:
      save_tasks(tasks)
      print(f"Task {task_id} marked as done.")
    else:
      print(f"Error: Task with ID {task_id} not found.")

# ---- Anything else is an unknown command ----
else:
  print(f"Error: Unknown command '{command}'.")
  print(
      "Available commands: add, list, update, delete, mark-in-progress,"
      " mark-done"
  )
