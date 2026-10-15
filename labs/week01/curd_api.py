from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

app: FastAPI = FastAPI()


class Task(BaseModel):
    title: str
    # Optional field to indicate if the task is done or not, defaulting to False
    done: bool = False


class TaskResponse(BaseModel):
    id: int
    task: Task


class TaskListResponse(BaseModel):
    tasks_list: list[TaskResponse]


# In-memory storage for tasks
TASKS: dict[int, Task] = {}


@app.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
async def create_task(task: Task) -> TaskResponse:
    if task.title == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task title cannot be empty",
        )

    task_id = len(TASKS) + 1
    TASKS[task_id] = task
    return TaskResponse(id=task_id, task=task)


@app.get("/tasks", status_code=status.HTTP_200_OK, response_model=TaskListResponse)
async def get_tasks() -> TaskListResponse:
    return TaskListResponse(
        tasks_list=[TaskResponse(id=id, task=task) for id, task in TASKS.items()]
    )


@app.get(
    "/tasks/{task_id}", status_code=status.HTTP_200_OK, response_model=TaskResponse
)
async def get_task(task_id: int) -> TaskResponse:
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return TaskResponse(id=task_id, task=task)


@app.put(
    "/tasks/{task_id}", status_code=status.HTTP_200_OK, response_model=TaskResponse
)
async def update_task(task_id: int, updated_task: Task) -> TaskResponse:
    if updated_task.title == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task title cannot be empty",
        )

    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    TASKS[task_id] = updated_task
    return TaskResponse(id=task_id, task=updated_task)


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int):
    if task_id not in TASKS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    del TASKS[task_id]
