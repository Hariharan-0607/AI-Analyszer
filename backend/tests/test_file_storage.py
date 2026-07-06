from app.services.file_storage import (
    proctoring_log_filename,
    slugify_project_title,
    tech_stack_filename,
    viva_evaluation_filename,
)


def test_slugify_project_title():
    assert slugify_project_title("FastAPI Todo CRUD") == "fastapi-todo-crud"
    assert slugify_project_title("  My Project!!!  ") == "my-project"
    assert slugify_project_title("") == "project"


def test_output_filenames_include_project_and_ids():
    title = "FastAPI Todo CRUD"
    analysis_id = "ana-ea4539ee30e5"
    session_id = "sess-6c8830c45620"

    assert (
        tech_stack_filename(analysis_id, title)
        == "fastapi-todo-crud__ana-ea4539ee30e5__tech_stack.json"
    )
    assert (
        proctoring_log_filename(session_id, analysis_id, title)
        == "fastapi-todo-crud__sess-6c8830c45620__ana-ea4539ee30e5__proctoring_log.json"
    )
    assert (
        viva_evaluation_filename(session_id, analysis_id, title)
        == "fastapi-todo-crud__sess-6c8830c45620__ana-ea4539ee30e5__viva_evaluation.json"
    )
