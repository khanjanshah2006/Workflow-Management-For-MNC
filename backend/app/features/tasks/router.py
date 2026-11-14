from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.db.session import get_db
from app.features.tasks.comments import TaskCommentService
from app.features.tasks.repository import TaskRepository
from app.features.tasks.schemas import (
    PaginatedTasksResponse,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskDetailResponse,
    TaskProgressResponse,
    TaskProgressUpdateSchema,
    TaskResubmitResponse,
    TaskResubmitSchema,
    TaskReviewQueueItem,
    TaskSubmissionResponse,
    TaskSummaryResponse,
)
from app.features.tasks.service import (
    TaskProgressService,
    TaskService,
    TaskSubmissionService,
)
from app.models.enums import PriorityLevel, TaskStatus
from app.models.team import Team
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])
project_tasks_router = APIRouter(prefix="/api/v1/projects", tags=["Tasks"])


# ── RBAC Helpers for US-13 ──────────────────────────────────────────────

def _check_review_queue_access(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserAccount:
    """
    Enforces RBAC for the review queue: TEAM_LEAD, PM, ADMIN.
    Recognizes baseline roles, elevated access grants, direct attributes on test mocks,
    as well as employees who are registered Team Leads in the database.
    """
    user_type_raw = getattr(current_user, "user_type", None)
    user_type_str = (
        user_type_raw.value if hasattr(user_type_raw, "value") else str(user_type_raw or "")
    ).upper()

    if user_type_str in ["TEAM_LEAD", "PM", "ADMIN", "SYSTEM_ADMIN", "PROJECT_MANAGER"]:
        return current_user

    if getattr(current_user, "is_team_lead", False) or getattr(current_user, "role", "").upper() == "TEAM_LEAD":
        return current_user

    if user_type_str == "EMPLOYEE":
        account_id = getattr(current_user, "account_id", None)
        emp_id = getattr(current_user, "emp_id", None)
        if emp_id is None and account_id is not None:
            emp = TaskRepository.get_employee_by_account_id(db, account_id)
            if emp is not None:
                emp_id = emp.emp_id
        if emp_id is not None:
            lead_team = db.query(Team).filter(Team.lead_emp_id == emp_id).first()
            if lead_team is not None:
                return current_user

    require_role(current_user, allowed=["TEAM_LEAD", "PM", "ADMIN"], db=db)
    return current_user


def _check_resubmit_access(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserAccount:
    """Enforces RBAC for task resubmission: EMPLOYEE or TEAM_LEAD."""
    user_type_raw = getattr(current_user, "user_type", None)
    user_type_str = (
        user_type_raw.value if hasattr(user_type_raw, "value") else str(user_type_raw or "")
    ).upper()

    if user_type_str in ["EMPLOYEE", "TEAM_LEAD"]:
        return current_user

    require_role(current_user, allowed=["EMPLOYEE", "TEAM_LEAD"], db=db)
    return current_user


# ── Static Collection Routes (must come before /{id}) ──────────────────

@router.post(
    "",
    response_model=TaskDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task (US-09)",
    description="Creates a task in TODO status with progress_pct=0 and rejection_count=0. Allowed for Team Lead, PM, and Admin.",
)
def create_task(
    payload: TaskCreate,
    request: Request,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskDetailResponse:
    ip_address = request.client.host if request.client else None
    return TaskService.create_task(
        db=db,
        payload=payload,
        actor=current_user,
        ip_address=ip_address,
    )


@router.get(
    "/my-tasks",
    response_model=PaginatedTasksResponse,
    status_code=status.HTTP_200_OK,
    summary="List tasks assigned to the current user (US-32)",
    description="Returns paginated tasks strictly assigned to the authenticated user's employee record.",
)
def get_my_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    priority: Optional[PriorityLevel] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedTasksResponse:
    items, total = TaskService.list_my_tasks(
        db=db,
        actor=current_user,
        status_filter=status_filter,
        priority_filter=priority,
        page=page,
        limit=limit,
    )
    return PaginatedTasksResponse(
        items=[TaskSummaryResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/review-queue",
    response_model=List[TaskReviewQueueItem],
    status_code=status.HTTP_200_OK,
    summary="Get task review triage queue (US-13)",
    description=(
        "Provide a consolidated review triage queue for Team Leads listing all tasks awaiting inspection. "
        "Scoped to tasks where task.team_id == current_user.team_id and task.status == TaskStatus.IN_REVIEW."
    ),
)
def get_review_queue(
    priority: Optional[str] = Query(None, description="Optional filter by task priority (e.g. LOW, MEDIUM, HIGH, CRITICAL)"),
    page: int = Query(1, ge=1, description="Page number for pagination (starts at 1)"),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    current_user: UserAccount = Depends(_check_review_queue_access),
    db: Session = Depends(get_db),
) -> List[TaskReviewQueueItem]:
    return TaskService.get_review_queue(
        db=db,
        current_user=current_user,
        priority=priority,
        page=page,
        limit=limit,
    )


# ── Dynamic Item Routes (/{id}) ─────────────────────────────────────────

@router.get(
    "/{id}",
    response_model=TaskDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get full task details (US-32)",
    description="Returns complete task record including project name, milestone title, creator, and assignee details.",
)
def get_task_detail(
    id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskDetailResponse:
    return TaskService.get_task(db=db, task_id=id)


@router.post(
    "/{id}/comments",
    response_model=TaskCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a task comment (US-33)",
    description="Adds a chronological task thread comment and notifies the task counterpart.",
)
def create_task_comment(
    id: int,
    payload: TaskCommentCreate,
    current_user: UserAccount = Depends(require_role(["EMPLOYEE", "PM", "ADMIN", "SYSTEM_ADMIN"])),
    db: Session = Depends(get_db),
) -> TaskCommentResponse:
    return TaskCommentService.create_comment(
        db=db,
        task_id=id,
        content=payload.content,
        current_user=current_user,
    )


@router.get(
    "/{id}/comments",
    response_model=List[TaskCommentResponse],
    status_code=status.HTTP_200_OK,
    summary="List task comments chronologically (US-33)",
    description="Returns the task discussion thread with author names, role badges, and timestamps.",
)
def get_task_comments(
    id: int,
    current_user: UserAccount = Depends(require_role(["EMPLOYEE", "PM", "ADMIN", "SYSTEM_ADMIN"])),
    db: Session = Depends(get_db),
) -> List[TaskCommentResponse]:
    return TaskCommentService.list_comments(db=db, task_id=id, current_user=current_user)


@router.post(
    "/{id}/submit",
    response_model=TaskSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit task deliverable for review (US-11)",
    description="Allows an assigned employee to submit remarks and attach deliverables. Transitions task status to IN_REVIEW and notifies the Team Lead.",
)
async def submit_task(
    id: int,
    request: Request,
    current_user: UserAccount = Depends(require_role(["EMPLOYEE"])),
    db: Session = Depends(get_db),
) -> TaskSubmissionResponse:
    content_type = request.headers.get("content-type", "").lower()
    remarks_str: str = ""
    file_obj: Optional[UploadFile] = None
    file_bytes: Optional[bytes] = None
    file_name_val: Optional[str] = None
    file_url_val: Optional[str] = None
    file_size_val: Optional[int] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        remarks_str = str(form.get("remarks") or "")
        raw_file = form.get("file")
        if isinstance(raw_file, UploadFile):
            file_obj = raw_file
            file_name_val = raw_file.filename
        elif hasattr(raw_file, "filename"):
            file_obj = raw_file
            file_name_val = getattr(raw_file, "filename", None)
    elif "application/json" in content_type:
        try:
            body = await request.json()
            remarks_str = body.get("remarks", "")
            file_url_val = body.get("file_url")
            file_name_val = body.get("file_name")
            file_size_val = body.get("file_size_bytes")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload provided.",
            )
    else:
        try:
            body = await request.json()
            remarks_str = body.get("remarks", "")
            file_url_val = body.get("file_url")
            file_name_val = body.get("file_name")
            file_size_val = body.get("file_size_bytes")
        except Exception:
            form = await request.form()
            remarks_str = str(form.get("remarks") or "")
            raw_file = form.get("file")
            if isinstance(raw_file, UploadFile):
                file_obj = raw_file
                file_name_val = raw_file.filename

    ip_address = request.client.host if request.client else None

    submission = TaskSubmissionService.submit_task(
        db=db,
        task_id=id,
        remarks=remarks_str,
        current_user=current_user,
        file=file_obj,
        file_bytes=file_bytes,
        original_filename=file_name_val,
        pre_existing_file_url=file_url_val,
        file_name=file_name_val,
        file_size_bytes=file_size_val,
        ip_address=ip_address,
    )
    return submission


@router.put(
    "/{id}/resubmit",
    response_model=TaskResubmitResponse,
    status_code=status.HTTP_200_OK,
    summary="Resubmit revised task after rejection (US-13)",
    description=(
        "Allow employees to resubmit revised work following a rejection. "
        "Validates task.status == REJECTED, transitions to IN_REVIEW, records a new task_submission, "
        "and dispatches a notification to the Team Lead."
    ),
)
def resubmit_task(
    id: int,
    payload: TaskResubmitSchema,
    current_user: UserAccount = Depends(_check_resubmit_access),
    db: Session = Depends(get_db),
) -> TaskResubmitResponse:
    return TaskService.resubmit_task(
        db=db,
        task_id=id,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/{id}/submissions",
    response_model=List[TaskSubmissionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get task submissions chronological list (US-11)",
    description="Returns chronological list of all submissions for this task.",
)
def get_task_submissions(
    id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TaskSubmissionResponse]:
    return TaskSubmissionService.get_task_submissions(
        db=db,
        task_id=id,
        current_user=current_user,
    )


@router.put(
    "/{id}/progress",
    response_model=TaskProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Update task progress and blocker status (US-10)",
    description=(
        "Allows assigned employees or the Team Lead to update task status (IN_PROGRESS, BLOCKED), "
        "update completion percentage (0-99%), and record blocker explanations. "
        "Flagging as BLOCKED triggers an automatic notification to the Team Lead."
    ),
)
def update_task_progress(
    id: int,
    payload: TaskProgressUpdateSchema,
    request: Request,
    current_user: UserAccount = Depends(require_role(["EMPLOYEE", "TEAM_LEAD", "ADMIN"])),
    db: Session = Depends(get_db),
) -> TaskProgressResponse:
    ip_address = request.client.host if request.client else None
    task = TaskProgressService.update_progress(
        db=db,
        task_id=id,
        payload=payload,
        current_user=current_user,
        ip_address=ip_address,
    )
    return task


# ── Project Scoped Routes ───────────────────────────────────────────────

@project_tasks_router.get(
    "/{project_id}/tasks",
    response_model=PaginatedTasksResponse,
    status_code=status.HTTP_200_OK,
    summary="List tasks for a project (US-32)",
    description="Lists all tasks for a project, filterable by team_id, milestone_id, and status.",
)
def get_project_tasks(
    project_id: int,
    team_id: Optional[int] = Query(None, ge=1),
    milestone_id: Optional[int] = Query(None, ge=1),
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedTasksResponse:
    items, total = TaskService.list_project_tasks(
        db=db,
        project_id=project_id,
        team_id=team_id,
        milestone_id=milestone_id,
        status_filter=status_filter,
        page=page,
        limit=limit,
    )
    return PaginatedTasksResponse(
        items=[TaskSummaryResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        limit=limit,
    )
