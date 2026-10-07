from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

app = FastAPI()

# In-memory storage for tasks
tasks = {}


class Task(BaseModel):
    title: str
    # Optional field to indicate if the task is done or not, defaulting to False
    done: bool = False


class TaskResponse(BaseModel):
    id: int
    task: Task


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]


@app.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
async def create_task(task: Task):
    if task.title == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task title cannot be empty",
        )

    task_id = len(tasks) + 1
    tasks[task_id] = task
    return TaskResponse(id=task_id, task=task)


@app.get("/tasks", status_code=status.HTTP_200_OK, response_model=TaskListResponse)
async def get_tasks():
    return TaskListResponse(
        tasks=[TaskResponse(id=id, task=task) for id, task in tasks.items()]
    )


@app.get(
    "/tasks/{task_id}", status_code=status.HTTP_200_OK, response_model=TaskResponse
)
async def get_task(task_id: int):
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return TaskResponse(id=task_id, task=task)


@app.put(
    "/tasks/{task_id}", status_code=status.HTTP_200_OK, response_model=TaskResponse
)
async def update_task(task_id: int, updated_task: Task):
    if updated_task.title == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task title cannot be empty",
        )

    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    tasks[task_id] = updated_task
    return TaskResponse(id=task_id, task=updated_task)


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int):
    if task_id not in tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    del tasks[task_id]
