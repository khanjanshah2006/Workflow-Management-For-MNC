"""
Executive Management Reports Engine (US-25, S7-BE-2).

Provides:
- Business validation for reporting periods (range <= 366 days, start <= today, end >= start).
- Strictly period-bounded metric aggregations across projects, milestones, tasks, deliverables, and signoffs.
- UTF-8 CSV report generation using Python's standard csv module.
- Multi-section PDF report generation via ReportLab (Cover, KPI summary, Department breakdown, Project health matrix, Deliverable signoff audit).
- Safe file persistence under REPORTS_DIR (defaults to <repo>/uploads/reports/) with sanitized user downloads.
- Audit logging with AuditAction.EXPORT on EXECUTIVE_REPORT entities.
"""

import csv
import io
import os
import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.features.executive.schemas import (
    ExecutiveReportCreateRequest,
    ExecutiveReportResponse,
    PaginatedExecutiveReportsResponse,
)
from app.models.client import Client
from app.models.deliverable import Deliverable, DeliverableFeedback
from app.models.department import Department
from app.models.enums import (
    AuditAction,
    DeliverableStatus,
    FeedbackDecision,
    MilestoneStatus,
    ReportFormat,
    TaskStatus,
)
from app.models.executive_report import ExecutiveReport
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.user_account import UserAccount


# ------------------------------------------------------------------
# Storage and Filename Helpers
# ------------------------------------------------------------------

def get_reports_dir() -> Path:
    """Return the absolute path to the reports storage directory, creating it if needed."""
    env_dir = os.getenv("REPORTS_DIR")
    if env_dir:
        path = Path(env_dir)
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        path = repo_root / "uploads" / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(title: str, ext: str) -> str:
    """Sanitize report title into safe download filename containing only [A-Za-z0-9_-]."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", title.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "executive_report"
    return f"{cleaned}.{ext.lower()}"


def validate_report_dates(
    period_start: date,
    period_end: date,
    today: Optional[date] = None,
) -> None:
    """
    Enforce S7-BE-2 business rules (raises HTTP 400 on failure):
    1. period_end >= period_start
    2. range <= 366 days
    3. period_start <= today
    """
    current_date = today or date.today()

    if period_end < period_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_end must be greater than or equal to period_start",
        )

    if (period_end - period_start).days > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reporting period range must not exceed 366 days.",
        )

    if period_start > current_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_start cannot be in the future.",
        )


# ------------------------------------------------------------------
# Metric Aggregation Layer
# ------------------------------------------------------------------

def collect_period_metrics(
    db: Session,
    period_start: date,
    period_end: date,
    today: Optional[date] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Collect period-bounded project metrics and deliverable signoffs.
    
    In-scope projects satisfy:
      start_date <= period_end AND (end_date IS NULL OR end_date >= period_start)
    """
    current_date = today or date.today()
    start_dt = datetime.combine(period_start, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end, time.max).replace(tzinfo=timezone.utc)
    cutoff_date = min(period_end, current_date)

    # 1. Fetch in-scope projects joined with their department attribution
    projects = (
        db.query(
            Project,
            Department.name.label("department_name"),
        )
        .outerjoin(ProjectManager, Project.pm_id == ProjectManager.pm_id)
        .outerjoin(Department, ProjectManager.dept_id == Department.dept_id)
        .filter(
            Project.start_date <= period_end,
            or_(Project.end_date.is_(None), Project.end_date >= period_start),
        )
        .order_by(Project.project_code.asc(), Project.project_id.asc())
        .all()
    )

    project_metrics: List[Dict[str, Any]] = []

    for proj, dept_name in projects:
        dept_str = dept_name or "Unassigned"
        proj_status = proj.status.value if hasattr(proj.status, "value") else str(proj.status)

        # Tasks completed in period
        tasks_in_period = (
            db.query(Task)
            .filter(
                Task.project_id == proj.project_id,
                Task.status == TaskStatus.DONE,
                Task.completed_at.isnot(None),
            )
            .all()
        )
        tasks_completed = sum(
            1
            for t in tasks_in_period
            if period_start <= (t.completed_at.date() if isinstance(t.completed_at, datetime) else t.completed_at) <= period_end
        )

        # Milestones due in period
        milestones_due = (
            db.query(func.count(ProjectMilestone.id))
            .filter(
                ProjectMilestone.project_id == proj.project_id,
                ProjectMilestone.target_date >= period_start,
                ProjectMilestone.target_date <= period_end,
                ProjectMilestone.is_deleted == False,
            )
            .scalar()
            or 0
        )

        # Milestones completed in period
        completed_ms_rows = (
            db.query(ProjectMilestone)
            .filter(
                ProjectMilestone.project_id == proj.project_id,
                ProjectMilestone.status == MilestoneStatus.COMPLETED,
                ProjectMilestone.completed_at.isnot(None),
                ProjectMilestone.is_deleted == False,
            )
            .all()
        )
        milestones_completed = sum(
            1
            for m in completed_ms_rows
            if period_start <= (m.completed_at.date() if isinstance(m.completed_at, datetime) else m.completed_at) <= period_end
        )

        # Deliverables submitted in period
        delivs_submitted_rows = (
            db.query(Deliverable)
            .filter(
                Deliverable.project_id == proj.project_id,
                Deliverable.submitted_at.isnot(None),
            )
            .all()
        )
        deliverables_submitted = sum(
            1
            for d in delivs_submitted_rows
            if period_start <= (d.submitted_at.date() if isinstance(d.submitted_at, datetime) else d.submitted_at) <= period_end
        )

        # Deliverables accepted in period
        fb_accepted_rows = (
            db.query(DeliverableFeedback.deliverable_id, DeliverableFeedback.given_at)
            .join(Deliverable, DeliverableFeedback.deliverable_id == Deliverable.deliverable_id)
            .filter(
                Deliverable.project_id == proj.project_id,
                DeliverableFeedback.decision == FeedbackDecision.ACCEPTED,
                DeliverableFeedback.given_at.isnot(None),
            )
            .all()
        )
        accepted_ids = {
            row[0]
            for row in fb_accepted_rows
            if period_start <= (row[1].date() if isinstance(row[1], datetime) else row[1]) <= period_end
        }
        # Direct accepted status check fallback
        for d in delivs_submitted_rows:
            if d.status == DeliverableStatus.ACCEPTED and d.submitted_at:
                d_date = d.submitted_at.date() if isinstance(d.submitted_at, datetime) else d.submitted_at
                if period_start <= d_date <= period_end:
                    accepted_ids.add(d.deliverable_id)
        deliverables_accepted = len(accepted_ids)

        # Average client rating in period
        feedbacks_in_period = (
            db.query(DeliverableFeedback.rating, DeliverableFeedback.given_at)
            .join(Deliverable, DeliverableFeedback.deliverable_id == Deliverable.deliverable_id)
            .filter(
                Deliverable.project_id == proj.project_id,
                DeliverableFeedback.rating.isnot(None),
                DeliverableFeedback.given_at.isnot(None),
            )
            .all()
        )
        valid_ratings = [
            row[0]
            for row in feedbacks_in_period
            if period_start <= (row[1].date() if isinstance(row[1], datetime) else row[1]) <= period_end
        ]
        avg_rating = round(sum(valid_ratings) / len(valid_ratings), 2) if valid_ratings else None

        # Overdue tasks at period end: due_date < min(period_end, today) and not completed by then
        proj_tasks = (
            db.query(Task)
            .filter(
                Task.project_id == proj.project_id,
                Task.due_date.isnot(None),
            )
            .all()
        )
        overdue_count = 0
        for t in proj_tasks:
            t_due = t.due_date.date() if isinstance(t.due_date, datetime) else t.due_date
            if t_due < cutoff_date:
                is_completed_by_cutoff = False
                if t.status == TaskStatus.DONE and t.completed_at is not None:
                    comp_date = (
                        t.completed_at.date()
                        if isinstance(t.completed_at, datetime)
                        else t.completed_at
                    )
                    if comp_date <= cutoff_date:
                        is_completed_by_cutoff = True
                if not is_completed_by_cutoff:
                    overdue_count += 1

        project_metrics.append({
            "project_id": proj.project_id,
            "project_code": proj.project_code,
            "project_name": proj.name,
            "department": dept_str,
            "status": proj_status,
            "tasks_completed": tasks_completed,
            "milestones_due": milestones_due,
            "milestones_completed": milestones_completed,
            "deliverables_submitted": deliverables_submitted,
            "deliverables_accepted": deliverables_accepted,
            "avg_client_rating": avg_rating,
            "overdue_tasks_at_period_end": overdue_count,
        })

    # 2. Collect deliverable feedback signoff audit records in the period
    all_feedbacks = (
        db.query(
            DeliverableFeedback,
            Deliverable.title.label("deliverable_title"),
            Project.name.label("project_name"),
            Project.project_code.label("project_code"),
            Client.company_name.label("client_company_name"),
        )
        .join(Deliverable, DeliverableFeedback.deliverable_id == Deliverable.deliverable_id)
        .join(Project, Deliverable.project_id == Project.project_id)
        .outerjoin(Client, Project.client_id == Client.client_id)
        .filter(DeliverableFeedback.given_at.isnot(None))
        .order_by(DeliverableFeedback.given_at.asc())
        .all()
    )

    signoff_rows: List[Dict[str, Any]] = []
    for fb, deliv_title, proj_name, proj_code, company_name in all_feedbacks:
        fb_date = fb.given_at.date() if isinstance(fb.given_at, datetime) else fb.given_at
        if period_start <= fb_date <= period_end:
            decision_val = (
                fb.decision.value if hasattr(fb.decision, "value") else str(fb.decision)
            )
            signoff_rows.append({
                "date": fb_date.strftime("%Y-%m-%d"),
                "project": proj_name or proj_code or "-",
                "deliverable": deliv_title or "-",
                "decision": decision_val,
                "rating": str(fb.rating) if fb.rating is not None else "-",
                "client": company_name or "-",
            })

    return project_metrics, signoff_rows


# ------------------------------------------------------------------
# CSV Generator
# ------------------------------------------------------------------

def generate_csv_report(project_metrics: List[Dict[str, Any]]) -> bytes:
    """Generate UTF-8 CSV bytes matching S7-BE-2 exact header specifications."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([
        "project_code",
        "project_name",
        "department",
        "status",
        "tasks_completed",
        "milestones_due",
        "milestones_completed",
        "deliverables_submitted",
        "deliverables_accepted",
        "avg_client_rating",
        "overdue_tasks_at_period_end",
    ])
    for row in project_metrics:
        rating_str = f"{row['avg_client_rating']:.2f}" if row["avg_client_rating"] is not None else ""
        writer.writerow([
            row["project_code"],
            row["project_name"],
            row["department"],
            row["status"],
            row["tasks_completed"],
            row["milestones_due"],
            row["milestones_completed"],
            row["deliverables_submitted"],
            row["deliverables_accepted"],
            rating_str,
            row["overdue_tasks_at_period_end"],
        ])
    return output.getvalue().encode("utf-8")


# ------------------------------------------------------------------
# PDF Generator (ReportLab)
# ------------------------------------------------------------------

def generate_pdf_report(
    report_title: str,
    period_start: date,
    period_end: date,
    generated_at: datetime,
    include_department_breakdown: bool,
    project_metrics: List[Dict[str, Any]],
    signoff_rows: List[Dict[str, Any]],
) -> bytes:
    """
    Generate professional multi-section executive management PDF report via ReportLab.
    Includes Cover, KPI Summary, Department Breakdown (optional), Project Health Matrix,
    and Deliverable Signoff Audit Table.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=report_title,
    )
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#111827"),
        alignment=0,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#4B5563"),
    )
    section_h2 = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1F2937"),
        spaceBefore=10,
        spaceAfter=6,
    )
    cell_header = ParagraphStyle(
        "CellHeader",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold",
        textColor=colors.whitesmoke,
        alignment=1,
    )
    cell_text = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1F2937"),
    )
    cell_center = ParagraphStyle(
        "CellCenter",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        alignment=1,
        textColor=colors.HexColor("#1F2937"),
    )

    elements: List[Any] = []

    # 1. Cover / Header
    elements.append(Paragraph(report_title, title_style))
    elements.append(Spacer(1, 4))
    gen_time_str = generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    elements.append(
        Paragraph(
            f"<b>Reporting Period:</b> {period_start} to {period_end} &nbsp;|&nbsp; "
            f"<b>Generated:</b> {gen_time_str} &nbsp;|&nbsp; "
            f"<b>Audience:</b> Executive Board &amp; Leadership",
            subtitle_style,
        )
    )
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB"), spaceAfter=12))

    # 2. Executive KPI Summary Cards / Table
    total_projects = len(project_metrics)
    total_tasks_completed = sum(p["tasks_completed"] for p in project_metrics)
    total_milestones_due = sum(p["milestones_due"] for p in project_metrics)
    total_milestones_completed = sum(p["milestones_completed"] for p in project_metrics)
    total_deliverables_submitted = sum(p["deliverables_submitted"] for p in project_metrics)
    total_deliverables_accepted = sum(p["deliverables_accepted"] for p in project_metrics)
    total_overdue = sum(p["overdue_tasks_at_period_end"] for p in project_metrics)

    all_ratings = [p["avg_client_rating"] for p in project_metrics if p["avg_client_rating"] is not None]
    overall_avg_rating = round(sum(all_ratings) / len(all_ratings), 2) if all_ratings else None
    rating_display = f"{overall_avg_rating} / 5.0" if overall_avg_rating is not None else "N/A"

    elements.append(Paragraph("Executive KPI Summary", section_h2))
    kpi_data = [
        [
            Paragraph("<b>Projects in Scope</b>", cell_center),
            Paragraph("<b>Tasks Completed</b>", cell_center),
            Paragraph("<b>Milestones (Done / Due)</b>", cell_center),
            Paragraph("<b>Deliverables (Accepted / Sub)</b>", cell_center),
            Paragraph("<b>Overdue Tasks</b>", cell_center),
            Paragraph("<b>Client Satisfaction</b>", cell_center),
        ],
        [
            Paragraph(f"<b>{total_projects}</b>", cell_center),
            Paragraph(f"<b>{total_tasks_completed}</b>", cell_center),
            Paragraph(f"<b>{total_milestones_completed} / {total_milestones_due}</b>", cell_center),
            Paragraph(f"<b>{total_deliverables_accepted} / {total_deliverables_submitted}</b>", cell_center),
            Paragraph(f"<b>{total_overdue}</b>", cell_center),
            Paragraph(f"<b>{rating_display}</b>", cell_center),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[85, 90, 105, 115, 75, 70])
    kpi_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F9FAFB")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    elements.append(kpi_table)
    elements.append(Spacer(1, 12))

    # 3. Department Breakdown (Only if flag is True)
    if include_department_breakdown:
        elements.append(Paragraph("Department Breakdown", section_h2))
        dept_map: Dict[str, Dict[str, Any]] = {}
        for p in project_metrics:
            d_name = p["department"]
            if d_name not in dept_map:
                dept_map[d_name] = {
                    "projects": 0,
                    "tasks_completed": 0,
                    "milestones_completed": 0,
                    "overdue_tasks": 0,
                }
            dept_map[d_name]["projects"] += 1
            dept_map[d_name]["tasks_completed"] += p["tasks_completed"]
            dept_map[d_name]["milestones_completed"] += p["milestones_completed"]
            dept_map[d_name]["overdue_tasks"] += p["overdue_tasks_at_period_end"]

        dept_rows = [[
            Paragraph("<b>Department</b>", cell_header),
            Paragraph("<b>Projects</b>", cell_header),
            Paragraph("<b>Tasks Completed</b>", cell_header),
            Paragraph("<b>Milestones Completed</b>", cell_header),
            Paragraph("<b>Overdue Tasks</b>", cell_header),
        ]]
        for d_name, d_stats in sorted(dept_map.items()):
            dept_rows.append([
                Paragraph(d_name, cell_text),
                Paragraph(str(d_stats["projects"]), cell_center),
                Paragraph(str(d_stats["tasks_completed"]), cell_center),
                Paragraph(str(d_stats["milestones_completed"]), cell_center),
                Paragraph(str(d_stats["overdue_tasks"]), cell_center),
            ])

        dept_table = Table(dept_rows, colWidths=[180, 80, 95, 105, 80])
        dept_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(dept_table)
        elements.append(Spacer(1, 12))

    # 4. Project Health Matrix
    elements.append(Paragraph("Project Health Matrix", section_h2))
    proj_rows = [[
        Paragraph("<b>Code</b>", cell_header),
        Paragraph("<b>Project Name</b>", cell_header),
        Paragraph("<b>Department</b>", cell_header),
        Paragraph("<b>Status</b>", cell_header),
        Paragraph("<b>Tasks Done</b>", cell_header),
        Paragraph("<b>Milestones</b>", cell_header),
        Paragraph("<b>Overdue</b>", cell_header),
        Paragraph("<b>Rating</b>", cell_header),
    ]]
    for p in project_metrics:
        r_str = f"{p['avg_client_rating']:.1f}" if p["avg_client_rating"] is not None else "-"
        proj_rows.append([
            Paragraph(p["project_code"], cell_center),
            Paragraph(p["project_name"], cell_text),
            Paragraph(p["department"], cell_text),
            Paragraph(p["status"], cell_center),
            Paragraph(str(p["tasks_completed"]), cell_center),
            Paragraph(f"{p['milestones_completed']} / {p['milestones_due']}", cell_center),
            Paragraph(str(p["overdue_tasks_at_period_end"]), cell_center),
            Paragraph(r_str, cell_center),
        ])

    proj_table = Table(proj_rows, colWidths=[65, 125, 95, 60, 55, 65, 45, 30])
    proj_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(proj_table)
    elements.append(Spacer(1, 12))

    # 5. Deliverable Signoff Audit Table
    elements.append(Paragraph("Deliverable Signoff Audit Table", section_h2))
    if signoff_rows:
        sign_rows = [[
            Paragraph("<b>Date</b>", cell_header),
            Paragraph("<b>Project</b>", cell_header),
            Paragraph("<b>Deliverable</b>", cell_header),
            Paragraph("<b>Decision</b>", cell_header),
            Paragraph("<b>Rating</b>", cell_header),
            Paragraph("<b>Client</b>", cell_header),
        ]]
        for s in signoff_rows:
            sign_rows.append([
                Paragraph(s["date"], cell_center),
                Paragraph(s["project"], cell_text),
                Paragraph(s["deliverable"], cell_text),
                Paragraph(s["decision"], cell_center),
                Paragraph(s["rating"], cell_center),
                Paragraph(s["client"], cell_text),
            ])
        sign_table = Table(sign_rows, colWidths=[70, 110, 130, 85, 45, 100])
        sign_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(sign_table)
    else:
        elements.append(
            Paragraph("No deliverable feedback recorded during this reporting period.", subtitle_style)
        )

    doc.build(elements)
    return buffer.getvalue()


# ------------------------------------------------------------------
# Executive Report Service
# ------------------------------------------------------------------

class ExecutiveReportService:
    """Service handling executive management report generation, persistence, listing, and download streaming."""

    @classmethod
    def generate_report(
        cls,
        db: Session,
        payload: ExecutiveReportCreateRequest,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> ExecutiveReportResponse:
        """
        Validate dates, compute period metrics, render PDF or CSV bytes,
        safely persist to disk, insert database row, and record EXPORT audit log.
        """
        validate_report_dates(payload.period_start, payload.period_end)

        now = datetime.now(timezone.utc)
        project_metrics, signoff_rows = collect_period_metrics(
            db=db,
            period_start=payload.period_start,
            period_end=payload.period_end,
            today=now.date(),
        )

        format_val = (
            payload.format.value if hasattr(payload.format, "value") else str(payload.format)
        ).upper()

        if format_val == "PDF":
            file_bytes = generate_pdf_report(
                report_title=payload.report_title.strip(),
                period_start=payload.period_start,
                period_end=payload.period_end,
                generated_at=now,
                include_department_breakdown=payload.include_department_breakdown,
                project_metrics=project_metrics,
                signoff_rows=signoff_rows,
            )
            ext = "pdf"
        elif format_val == "CSV":
            file_bytes = generate_csv_report(project_metrics=project_metrics)
            ext = "csv"
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported report format: {format_val}. Must be PDF or CSV.",
            )

        # 1. Insert preliminary row to obtain sequential report_id
        report = ExecutiveReport(
            generated_by_account_id=current_user.account_id,
            report_title=payload.report_title.strip(),
            period_start=payload.period_start,
            period_end=payload.period_end,
            report_format=ReportFormat[format_val],
            include_department_breakdown=payload.include_department_breakdown,
            file_path="",  # Updated after disk write
            file_size_bytes=len(file_bytes),
        )
        db.add(report)
        db.flush()

        # 2. Persist file to storage directory using sanitized internal name: exec_report_{id}_{yyyymmdd}.{ext}
        now_str = now.strftime("%Y%m%d")
        safe_filename = f"exec_report_{report.report_id}_{now_str}.{ext}"
        storage_path = get_reports_dir() / safe_filename

        try:
            with open(storage_path, "wb") as f:
                f.write(file_bytes)
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to persist report file: {str(exc)}",
            )

        report.file_path = str(storage_path)

        # 3. Write EXPORT audit log
        write_audit_log(
            db=db,
            action=AuditAction.EXPORT,
            entity_name="EXECUTIVE_REPORT",
            entity_ref_id=str(report.report_id),
            account_id=current_user.account_id,
            old_value=None,
            new_value={
                "report_id": report.report_id,
                "report_title": report.report_title,
                "format": format_val,
                "period_start": str(report.period_start),
                "period_end": str(report.period_end),
                "file_size_bytes": report.file_size_bytes,
            },
            ip_address=ip_address,
        )

        db.commit()
        db.refresh(report)

        return ExecutiveReportResponse.from_orm_report(report)

    @classmethod
    def list_reports(
        cls,
        db: Session,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedExecutiveReportsResponse:
        """Paginated history of all executive reports, newest first."""
        query = db.query(ExecutiveReport).order_by(
            ExecutiveReport.generated_at.desc(),
            ExecutiveReport.report_id.desc(),
        )
        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        return PaginatedExecutiveReportsResponse(
            items=[ExecutiveReportResponse.from_orm_report(r) for r in items],
            total=total,
            page=page,
            limit=limit,
        )

    @classmethod
    def get_report_by_id(cls, db: Session, report_id: int) -> ExecutiveReportResponse:
        """Retrieve metadata for a specific executive report."""
        report = (
            db.query(ExecutiveReport)
            .filter(ExecutiveReport.report_id == report_id)
            .first()
        )
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Executive report with ID {report_id} not found.",
            )
        return ExecutiveReportResponse.from_orm_report(report)

    @classmethod
    def get_report_download_info(cls, db: Session, report_id: int) -> Tuple[str, str, str]:
        """
        Validate report existence and disk presence.
        Returns (absolute_file_path, media_type, sanitized_download_filename).
        """
        report = (
            db.query(ExecutiveReport)
            .filter(ExecutiveReport.report_id == report_id)
            .first()
        )
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Executive report with ID {report_id} not found.",
            )

        if not os.path.exists(report.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report file no longer exists on disk.",
            )

        ext = "pdf" if report.report_format == ReportFormat.PDF else "csv"
        media_type = "application/pdf" if ext == "pdf" else "text/csv; charset=utf-8"
        download_name = sanitize_filename(report.report_title, ext)

        return report.file_path, media_type, download_name
