from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.models.enums import AuditAction
from app.models.user_account import UserAccount
from app.models.employee import Employee
from app.features.profile.repository import ProfileRepository
from app.features.profile.schemas import (
    ProfileResponse,
    ProfileUpdateRequest,
    SkillResponse,
    DepartmentInfo,
    ManagerInfo,
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

        # Persist permitted update
        updated_employee = ProfileRepository.update_employee_contact(
            db=db,
            employee=employee,
            phone=payload.phone,
        )

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
