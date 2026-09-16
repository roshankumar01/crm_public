from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course, Lead, Learner, LearnerCourseRecord, MarketingCampaign, User
from app.services.auth import get_current_user, require_admin
from app.services.course_rules import is_completed
from app.services.lead_workflow import sync_opportunity_leads
from app.services.recommendation import get_recommendations

router = APIRouter(prefix="/learners", tags=["Learners"])


@router.get("")
def get_learners(
    search: str | None = Query(default=None),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(Learner)
    if search:
        text = f"%{search.strip()}%"
        query = query.where(
            or_(
                Learner.name.ilike(text),
                Learner.learner_number.ilike(text),
                Learner.email_id.ilike(text),
            )
        )

    learners = db.execute(
        query.order_by(Learner.last_activity_date.desc().nullslast())
    ).scalars().all()

    return [
        {
            "learner_number": learner.learner_number,
            "name": learner.name,
            "nationality": learner.nationality,
            "contact_number": learner.contact_number,
            "email_id": learner.email_id,
            "last_activity_date": learner.last_activity_date,
        }
        for learner in learners
    ]


@router.get("/{learner_number}")
def get_learner(
    learner_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    learner = db.get(Learner, learner_number)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found.")

    if current_user.role != "ADMIN":
        sync_opportunity_leads(db)
        assigned = db.scalar(
            select(Lead.id).where(
                Lead.learner_number == learner_number,
                Lead.assigned_to_user_id == current_user.id,
            )
        )
        if not assigned:
            raise HTTPException(status_code=403, detail="This learner is not assigned to you.")

    history_rows = db.execute(
        select(LearnerCourseRecord, Course)
        .join(Course, LearnerCourseRecord.course_id == Course.id)
        .where(LearnerCourseRecord.learner_number == learner_number)
        .order_by(LearnerCourseRecord.event_date, LearnerCourseRecord.id)
    ).all()
    campaigns = db.execute(
        select(MarketingCampaign)
        .where(MarketingCampaign.learner_number == learner_number)
        .order_by(MarketingCampaign.created_at.desc(), MarketingCampaign.id.desc())
    ).scalars().all()

    timeline = []
    completed = []
    for record, course in history_rows:
        title = (
            f"{course.name} - {record.result}"
            if record.result
            else f"{course.name} - {record.enrollment_status}"
            if record.enrollment_status
            else f"{course.name} activity"
        )
        timeline.append({
            "id": record.id,
            "date": record.event_date,
            "event_type": record.event_type,
            "course_code": course.code,
            "program_code": course.program_code,
            "course_name": course.name,
            "result": record.result,
            "enrollment_status": record.enrollment_status,
            "title": title,
            "details": record.details,
        })
        if is_completed(record):
            completed.append(course.code)

    return {
        "learner": {
            "learner_number": learner.learner_number,
            "name": learner.name,
            "nationality": learner.nationality,
            "contact_number": learner.contact_number,
            "email_id": learner.email_id,
            "last_activity_date": learner.last_activity_date,
        },
        "passed_courses": list(dict.fromkeys(completed)),
        "recommendations": get_recommendations(history_rows),
        "timeline": timeline,
        "campaigns": [{
            "id": campaign.id,
            "marketing_type": campaign.marketing_type,
            "campaign_name": campaign.campaign_name,
            "created_at": campaign.created_at,
        } for campaign in campaigns],
    }
