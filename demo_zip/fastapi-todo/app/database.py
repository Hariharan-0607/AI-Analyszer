from app.models import TodoCreate, TodoResponse, TodoUpdate

_todos: dict[int, dict] = {}
_next_id = 1


def list_todos() -> list[TodoResponse]:
    return [TodoResponse(id=t["id"], **{k: v for k, v in t.items() if k != "id"}) for t in _todos.values()]


def get_todo(todo_id: int) -> TodoResponse | None:
    item = _todos.get(todo_id)
    if not item:
        return None
    return TodoResponse(id=item["id"], title=item["title"], description=item["description"], completed=item["completed"])


def create_todo(data: TodoCreate) -> TodoResponse:
    global _next_id
    todo = {"id": _next_id, **data.model_dump()}
    _todos[_next_id] = todo
    _next_id += 1
    return TodoResponse(**todo)


def update_todo(todo_id: int, data: TodoUpdate) -> TodoResponse | None:
    item = _todos.get(todo_id)
    if not item:
        return None
    updates = data.model_dump(exclude_unset=True)
    item.update(updates)
    return TodoResponse(id=item["id"], title=item["title"], description=item["description"], completed=item["completed"])


def delete_todo(todo_id: int) -> bool:
    return _todos.pop(todo_id, None) is not None
