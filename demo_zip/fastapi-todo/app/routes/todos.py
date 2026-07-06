from fastapi import APIRouter, HTTPException

from app.database import create_todo, delete_todo, get_todo, list_todos, update_todo
from app.models import TodoCreate, TodoResponse, TodoUpdate

router = APIRouter()


@router.get("/", response_model=list[TodoResponse])
def get_all_todos():
    return list_todos()


@router.get("/{todo_id}", response_model=TodoResponse)
def get_single_todo(todo_id: int):
    todo = get_todo(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


@router.post("/", response_model=TodoResponse, status_code=201)
def create_new_todo(data: TodoCreate):
    return create_todo(data)


@router.put("/{todo_id}", response_model=TodoResponse)
def update_existing_todo(todo_id: int, data: TodoUpdate):
    todo = update_todo(todo_id, data)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


@router.delete("/{todo_id}", status_code=204)
def remove_todo(todo_id: int):
    if not delete_todo(todo_id):
        raise HTTPException(status_code=404, detail="Todo not found")
