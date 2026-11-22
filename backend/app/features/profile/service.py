from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import scope
from app.core.audit import write_audit_log
from app.core.notification_types import SKILL_REQUEST_CREATED, SKILL_REQUEST_DECIDED
from app.features.notifications.service import NotificationService
from app.models.enums import (
    AuditAction,
    CommonStatus,
    SkillProficiency,
    SkillRequestAction,
    SkillRequestStatus,
    UserType,
)
from app.models.user_account import UserAccount
from app.models.employee import Employee
from app.models.skill import Skill, SkillChangeRequest
from app.models.team import TeamMember
from app.features.profile.repository import ProfileRepository
from app.features.profile.schemas import (
    ProfileResponse,
    ProfileUpdateRequest,
    SkillResponse,
    DepartmentInfo,
    ManagerInfo,
    SkillChangeRequestCreate,
    SkillChangeDecisionIn,
    SkillChangeRequestOut,
    PaginatedSkillChangeRequestsOut,
)


class ProfileService:
    """Service layer handling business logic for employee self-service profile (US-03)."""

    @classmethod
    def _build_profile_response(cls, db: Session, employee: Employee) -> ProfileResponse:
        """Helper to assemble a ProfileResponse with linked department and manager/lead info."""
        dept_info = None
        if employee.dept_id:
            dept = ProfileRepository.get_department(db, employee.dept_id)
            if dept:
                dept_info = DepartmentInfo.model_validate(dept)

        manager_info = None
        lead = ProfileRepository.get_manager_or_lead(db, employee)
        if lead:
            manager_info = ManagerInfo.model_validate(lead)

        return ProfileResponse(
            emp_id=employee.emp_id,
            account_id=employee.account_id,
            emp_code=employee.emp_code,
            full_name=employee.full_name,
            email=employee.email,
            phone=employee.phone,
            designation=employee.designation,
            date_of_joining=employee.date_of_joining,
            status=employee.status,
            department=dept_info,
            manager=manager_info,
            emergency_contact=getattr(employee, "emergency_contact", None),
            bio=getattr(employee, "bio", None),
        )

    @classmethod
    def get_my_profile(cls, db: Session, current_user: UserAccount) -> ProfileResponse:
        """Retrieve the authenticated employee's full organizational profile."""
        employee = ProfileRepository.get_by_account_id(db, current_user.account_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee profile not found for the authenticated user account",
            )

        return cls._build_profile_response(db, employee)

    @classmethod
    def update_my_profile(
        cls,
        db: Session,
        payload: ProfileUpdateRequest,
        current_user: UserAccount,
        ip_address: Optional[str] = None,
    ) -> ProfileResponse:
        """
        Update permitted self-service contact fields for the authenticated employee.
        Triggers an audit log record for state compliance.
        """
        employee = ProfileRepository.get_by_account_id(db, current_user.account_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee profile not found for the authenticated user account",
            )

        # Capture old values for audit logging
        old_values = {
            "phone": employee.phone,
        }

        # New values submitted
        new_values = {}
        if payload.phone is not None:
            new_values["phone"] = payload.phone
        if payload.address is not None:
            new_values["address"] = payload.address
        if payload.emergency_contact is not None:
            new_values["emergency_contact"] = payload.emergency_contact
        if payload.bio is not None:
            new_values["bio"] = payload.bio

        # Persist permitted update
        updated_employee = ProfileRepository.update_employee_contact(
            db=db,
            employee=employee,
            phone=payload.phone,
        )

        if payload.emergency_contact is not None:
            setattr(updated_employee, "emergency_contact", payload.emergency_contact)
        if payload.bio is not None:
            setattr(updated_employee, "bio", payload.bio)

        # Audit log recording state changes
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="EMPLOYEE",
            entity_ref_id=str(updated_employee.emp_id),
            account_id=current_user.account_id,
            old_value=old_values,
            new_value=new_values,
            ip_address=ip_address,
        )

        return cls._build_profile_response(db, updated_employee)

    @classmethod
    def get_my_skills(cls, db: Session, current_user: UserAccount) -> List[SkillResponse]:
        """Fetch all skills assigned to the authenticated employee with proficiency ratings."""
        employee = ProfileRepository.get_by_account_id(db, current_user.account_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee profile not found for the authenticated user account",
            )

        skills_data = ProfileRepository.get_employee_skills(db, employee.emp_id)
        return [SkillResponse.model_validate(s) for s in skills_data]

    # ── US-34 Skill Proposals Service Methods ────────────────────────────────

    @classmethod
    def _to_request_out(
        cls,
        req: SkillChangeRequest,
        employee_name: Optional[str] = None,
        skill_name: Optional[str] = None,
    ) -> SkillChangeRequestOut:
        return SkillChangeRequestOut(
            request_id=req.request_id,
            emp_id=req.emp_id,
            employee_name=employee_name,
            action=req.action,
            skill_id=req.skill_id,
            skill_name=skill_name or (req.skill.name if getattr(req, "skill", None) else None),
            proposed_skill_name=req.proposed_skill_name,
            proficiency=req.proficiency,
            years_of_experience=req.years_of_experience,
            justification=req.justification,
            status=req.status,
            remarks=req.remarks,
            reviewed_by_account_id=req.reviewed_by_account_id,
            reviewed_at=req.reviewed_at,
            created_at=req.created_at,
        )

    @classmethod
    def propose_skill_change(
        cls,
        db: Session,
        current_user: UserAccount,
        data: SkillChangeRequestCreate,
    ) -> SkillChangeRequestOut:
        """
        Submit a new skill change proposal (ADD, UPDATE, or REMOVE).
        Enforces one pending request per skill, notifies HR & Team Leads,
        and logs audit trail (US-34).
        """
        emp = scope.resolve_employee(db, current_user)
        if not emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee profile not found for authenticated account",
            )

        # Validate action requirements
        if data.action == SkillRequestAction.ADD:
            if not data.skill_id and (not data.proposed_skill_name or not data.proposed_skill_name.strip()):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either skill_id or proposed_skill_name is required when proposing an ADD action",
                )
            if data.proficiency is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Proficiency is required when proposing an ADD action",
                )
            if data.skill_id:
                skill = ProfileRepository.get_skill(db, data.skill_id)
                if not skill:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Referenced skill does not exist",
                    )
                existing_emp_skill = ProfileRepository.get_employee_skill(db, emp.emp_id, data.skill_id)
                if existing_emp_skill:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Skill is already assigned to your profile; submit an UPDATE proposal instead",
                    )

        elif data.action == SkillRequestAction.UPDATE:
            if not data.skill_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="skill_id is required when proposing an UPDATE action",
                )
            if data.proficiency is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Proficiency is required when proposing an UPDATE action",
                )
            existing_emp_skill = ProfileRepository.get_employee_skill(db, emp.emp_id, data.skill_id)
            if not existing_emp_skill:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Skill is not currently assigned to your profile",
                )

        elif data.action == SkillRequestAction.REMOVE:
            if not data.skill_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="skill_id is required when proposing a REMOVE action",
                )
            existing_emp_skill = ProfileRepository.get_employee_skill(db, emp.emp_id, data.skill_id)
            if not existing_emp_skill:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Skill is not currently assigned to your profile",
                )

        # Check for existing pending request on the same skill
        pending = ProfileRepository.get_pending_request_for_skill(
            db=db,
            emp_id=emp.emp_id,
            skill_id=data.skill_id,
            proposed_skill_name=data.proposed_skill_name,
        )
        if pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pending request already exists for this skill",
            )

        # Create proposal record
        req = ProfileRepository.create_skill_change_request(
            db=db,
            emp_id=emp.emp_id,
            action=data.action,
            skill_id=data.skill_id,
            proposed_skill_name=data.proposed_skill_name,
            proficiency=data.proficiency,
            years_of_experience=data.years_of_experience,
            justification=data.justification,
        )

        # Audit log creation
        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="SKILL_CHANGE_REQUEST",
            entity_ref_id=str(req.request_id),
            account_id=current_user.account_id,
            new_value={
                "emp_id": emp.emp_id,
                "action": req.action.value,
                "skill_id": req.skill_id,
                "proposed_skill_name": req.proposed_skill_name,
                "proficiency": req.proficiency.value if req.proficiency else None,
                "years_of_experience": req.years_of_experience,
                "justification": req.justification,
            },
            commit=False,
        )

        # Notify HR accounts and applicant's active Team Lead(s)
        hr_stmt = select(UserAccount.account_id).where(
            UserAccount.user_type.in_([UserType.HR, "HR", "HR_MANAGER"]),
            UserAccount.status == CommonStatus.ACTIVE,
        )
        hr_account_ids = list(db.scalars(hr_stmt))
        tl_account_ids = scope.team_lead_account_ids_for(db, emp.emp_id)
        recipients = set(hr_account_ids) | set(tl_account_ids)
        recipients.discard(current_user.account_id)

        skill_display = (
            data.proposed_skill_name
            or (ProfileRepository.get_skill(db, data.skill_id).name if data.skill_id else "Skill")
        )
        for rec_id in recipients:
            NotificationService.create_notification(
                db=db,
                user_id=rec_id,
                type=SKILL_REQUEST_CREATED,
                title="New Skill Change Proposal",
                message=f"{emp.full_name} submitted a skill proposal ({req.action.value}: {skill_display}).",
                link=f"/skills/requests/{req.request_id}",
            )

        db.commit()
        db.refresh(req)

        skill_name = None
        if req.skill_id:
            s_obj = ProfileRepository.get_skill(db, req.skill_id)
            if s_obj:
                skill_name = s_obj.name

        return cls._to_request_out(req, employee_name=emp.full_name, skill_name=skill_name)

    @classmethod
    def list_my_skill_requests(
        cls,
        db: Session,
        current_user: UserAccount,
    ) -> List[SkillChangeRequestOut]:
        """Fetch all skill proposals submitted by current employee, newest first."""
        emp = scope.resolve_employee(db, current_user)
        if not emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee profile not found for authenticated account",
            )
        records = ProfileRepository.list_my_skill_requests(db, emp.emp_id)
        return [cls._to_request_out(r, emp_name, s_name) for r, emp_name, s_name in records]

    @classmethod
    def list_skill_requests_queue(
        cls,
        db: Session,
        current_user: UserAccount,
        status_filter: Optional[SkillRequestStatus] = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedSkillChangeRequestsOut:
        """
        Review queue for skill proposals (US-34).
        HR and Admin roles see all requests; Team Leads see requests from members of active teams they lead.
        """
        is_hr_or_admin = current_user.user_type in (
            UserType.HR, "HR", "HR_MANAGER",
            UserType.ADMIN, "ADMIN",
            UserType.SYSTEM_ADMIN, "SYSTEM_ADMIN",
        )

        allowed_emp_ids: Optional[List[int]] = None
        if not is_hr_or_admin:
            reviewer_emp = scope.resolve_employee(db, current_user)
            if not reviewer_emp:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view the skill review queue",
                )
            led_teams = scope.led_team_ids(db, reviewer_emp.emp_id)
            if not led_teams:
                return PaginatedSkillChangeRequestsOut(items=[], total=0, page=page, limit=limit)

            stmt = select(TeamMember.emp_id).where(TeamMember.team_id.in_(led_teams)).distinct()
            allowed_emp_ids = list(db.scalars(stmt))
            if not allowed_emp_ids:
                return PaginatedSkillChangeRequestsOut(items=[], total=0, page=page, limit=limit)

        total = ProfileRepository.count_review_requests(
            db, status_filter=status_filter, allowed_emp_ids=allowed_emp_ids
        )
        records = ProfileRepository.list_review_requests(
            db,
            status_filter=status_filter,
            allowed_emp_ids=allowed_emp_ids,
            page=page,
            limit=limit,
        )
        items = [cls._to_request_out(r, emp_name, s_name) for r, emp_name, s_name in records]
        return PaginatedSkillChangeRequestsOut(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    @classmethod
    def approve_skill_request(
        cls,
        db: Session,
        current_user: UserAccount,
        request_id: int,
        payload: SkillChangeDecisionIn,
    ) -> SkillChangeRequestOut:
        """
        Approve a pending skill change request and apply the changes to employee_skill (US-34).
        Authorized for HR/Admin or the Team Lead of the applicant.
        """
        item = ProfileRepository.get_skill_change_request_with_details(db, request_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Skill change request not found",
            )
        req, emp_name, skill_name = item

        if req.status != SkillRequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Skill request is already {req.status.value.lower()}",
            )

        is_hr_or_admin = current_user.user_type in (
            UserType.HR, "HR", "HR_MANAGER",
            UserType.ADMIN, "ADMIN",
            UserType.SYSTEM_ADMIN, "SYSTEM_ADMIN",
        )
        reviewer_emp = scope.resolve_employee(db, current_user)
        if not is_hr_or_admin:
            if not reviewer_emp or not scope.is_team_lead_of(db, reviewer_emp.emp_id, req.emp_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to decide this skill request",
                )
            if reviewer_emp.emp_id == req.emp_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot decide your own skill proposal",
                )

        # Apply skill modifications to employee_skill table
        if req.action == SkillRequestAction.ADD:
            skill_id = req.skill_id
            if not skill_id and req.proposed_skill_name:
                existing_skill = ProfileRepository.get_skill_by_name(db, req.proposed_skill_name)
                if existing_skill:
                    skill_id = existing_skill.skill_id
                else:
                    new_skill = ProfileRepository.create_skill(db, name=req.proposed_skill_name)
                    skill_id = new_skill.skill_id
                req.skill_id = skill_id

            emp_skill = ProfileRepository.get_employee_skill(db, req.emp_id, skill_id)
            if emp_skill:
                if req.proficiency:
                    emp_skill.proficiency = req.proficiency
                emp_skill.years_of_experience = req.years_of_experience
            else:
                ProfileRepository.create_employee_skill(
                    db=db,
                    emp_id=req.emp_id,
                    skill_id=skill_id,
                    proficiency=req.proficiency or SkillProficiency.BEGINNER,
                    years_of_experience=req.years_of_experience,
                )

        elif req.action == SkillRequestAction.UPDATE:
            emp_skill = ProfileRepository.get_employee_skill(db, req.emp_id, req.skill_id)
            if emp_skill:
                if req.proficiency:
                    emp_skill.proficiency = req.proficiency
                emp_skill.years_of_experience = req.years_of_experience
            else:
                ProfileRepository.create_employee_skill(
                    db=db,
                    emp_id=req.emp_id,
                    skill_id=req.skill_id,
                    proficiency=req.proficiency or SkillProficiency.BEGINNER,
                    years_of_experience=req.years_of_experience,
                )

        elif req.action == SkillRequestAction.REMOVE:
            emp_skill = ProfileRepository.get_employee_skill(db, req.emp_id, req.skill_id)
            if emp_skill:
                ProfileRepository.delete_employee_skill(db, emp_skill)

        # Update request state
        req.status = SkillRequestStatus.APPROVED
        req.remarks = payload.remarks.strip() if payload.remarks else None
        req.reviewed_by_account_id = current_user.account_id
        req.reviewed_at = datetime.now(timezone.utc)

        # Notify applicant
        applicant = db.scalar(select(Employee).where(Employee.emp_id == req.emp_id))
        if applicant and applicant.account_id:
            display_skill = req.proposed_skill_name or skill_name or "Skill"
            remarks_suffix = f" Remarks: {req.remarks}" if req.remarks else ""
            NotificationService.create_notification(
                db=db,
                user_id=applicant.account_id,
                type=SKILL_REQUEST_DECIDED,
                title="Skill Change Proposal Approved",
                message=f"Your skill proposal ({req.action.value}: {display_skill}) has been approved.{remarks_suffix}",
                link="/profile/me/skills",
            )

        # Audit log decision
        write_audit_log(
            db=db,
            action=AuditAction.APPROVE,
            entity_name="SKILL_CHANGE_REQUEST",
            entity_ref_id=str(req.request_id),
            account_id=current_user.account_id,
            old_value={"status": SkillRequestStatus.PENDING.value},
            new_value={"status": req.status.value, "remarks": req.remarks},
            commit=False,
        )

        db.commit()
        db.refresh(req)

        if not skill_name and req.skill_id:
            s_obj = ProfileRepository.get_skill(db, req.skill_id)
            skill_name = s_obj.name if s_obj else None

        return cls._to_request_out(req, employee_name=emp_name, skill_name=skill_name)

    @classmethod
    def reject_skill_request(
        cls,
        db: Session,
        current_user: UserAccount,
        request_id: int,
        payload: SkillChangeDecisionIn,
    ) -> SkillChangeRequestOut:
        """
        Reject a pending skill change request with mandatory remarks (US-34).
        Authorized for HR/Admin or the Team Lead of the applicant.
        """
        item = ProfileRepository.get_skill_change_request_with_details(db, request_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Skill change request not found",
            )
        req, emp_name, skill_name = item

        if not payload.remarks or not payload.remarks.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Remarks are mandatory when rejecting a skill proposal",
            )

        if req.status != SkillRequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Skill request is already {req.status.value.lower()}",
            )

        is_hr_or_admin = current_user.user_type in (
            UserType.HR, "HR", "HR_MANAGER",
            UserType.ADMIN, "ADMIN",
            UserType.SYSTEM_ADMIN, "SYSTEM_ADMIN",
        )
        reviewer_emp = scope.resolve_employee(db, current_user)
        if not is_hr_or_admin:
            if not reviewer_emp or not scope.is_team_lead_of(db, reviewer_emp.emp_id, req.emp_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to decide this skill request",
                )
            if reviewer_emp.emp_id == req.emp_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot decide your own skill proposal",
                )

        req.status = SkillRequestStatus.REJECTED
        req.remarks = payload.remarks.strip()
        req.reviewed_by_account_id = current_user.account_id
        req.reviewed_at = datetime.now(timezone.utc)

        applicant = db.scalar(select(Employee).where(Employee.emp_id == req.emp_id))
        if applicant and applicant.account_id:
            display_skill = req.proposed_skill_name or skill_name or "Skill"
            NotificationService.create_notification(
                db=db,
                user_id=applicant.account_id,
                type=SKILL_REQUEST_DECIDED,
                title="Skill Change Proposal Rejected",
                message=f"Your skill proposal ({req.action.value}: {display_skill}) has been rejected. Remarks: {req.remarks}",
                link="/profile/me/skills",
            )

        write_audit_log(
            db=db,
            action=AuditAction.REJECT,
            entity_name="SKILL_CHANGE_REQUEST",
            entity_ref_id=str(req.request_id),
            account_id=current_user.account_id,
            old_value={"status": SkillRequestStatus.PENDING.value},
            new_value={"status": req.status.value, "remarks": req.remarks},
            commit=False,
        )

        db.commit()
        db.refresh(req)

        if not skill_name and req.skill_id:
            s_obj = ProfileRepository.get_skill(db, req.skill_id)
            skill_name = s_obj.name if s_obj else None

        return cls._to_request_out(req, employee_name=emp_name, skill_name=skill_name)
