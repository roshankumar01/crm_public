from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Lead, LeadActivity, Learner, LearnerCourseRecord, User
from app.services.course_rules import build_learner_opportunities

VALID_LEAD_STATUSES = ("NEW", "IN_CONTACT", "REJECTED", "CONVERTED")
VALID_ACTIVITY_TYPES = ("EMAIL_CAMPAIGN", "WHATSAPP_CAMPAIGN", "CALL", "NOTE")


def sync_opportunity_leads(db: Session):
    history_rows = db.execute(
        select(LearnerCourseRecord, Course)
        .join(Course, LearnerCourseRecord.course_id == Course.id)
        .order_by(
            LearnerCourseRecord.learner_number,
            LearnerCourseRecord.event_date,
            LearnerCourseRecord.id,
        )
    ).all()

    history_by_learner = defaultdict(list)
    for record, course in history_rows:
        history_by_learner[record.learner_number].append((record, course))

    existing_leads = db.execute(select(Lead)).scalars().all()
    by_key = {(lead.learner_number, lead.opportunity_key): lead for lead in existing_leads}
    current_keys = set()

    learner_numbers = db.execute(select(Learner.learner_number)).scalars().all()
    for learner_number in learner_numbers:
        opportunities = build_learner_opportunities(history_by_learner.get(learner_number, []))
        for opportunity in opportunities:
            key = (learner_number, opportunity["key"])
            current_keys.add(key)
            lead = by_key.get(key)
            if lead is None:
                lead = Lead(
                    learner_number=learner_number,
                    opportunity_key=opportunity["key"],
                    target_code=opportunity["target_code"],
                    trigger_date=opportunity.get("trigger_date"),
                    status="NEW",
                    is_active=True,
                )
                db.add(lead)
                by_key[key] = lead
            else:
                lead.target_code = opportunity["target_code"]
                lead.trigger_date = opportunity.get("trigger_date")
                lead.is_active = True

    for key, lead in by_key.items():
        if key not in current_keys:
            lead.is_active = False

    db.commit()


def get_accessible_lead(db: Session, lead_id: int, current_user: User) -> Lead:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    if current_user.role == "ADMIN":
        return lead
    if lead.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This lead is not assigned to you.")
    return lead


def change_lead_status(db: Session, lead: Lead, status: str, user: User):
    normalized = status.strip().upper()
    if normalized not in VALID_LEAD_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(VALID_LEAD_STATUSES)}.",
        )

    previous = lead.status
    if previous == normalized:
        return lead

    lead.status = normalized
    lead.status_updated_at = datetime.now(timezone.utc)
    db.add(
        LeadActivity(
            lead_id=lead.id,
            user_id=user.id,
            activity_type="STATUS_CHANGE",
            channel="SYSTEM",
            notes=f"Status changed from {previous} to {normalized}.",
        )
    )
    db.commit()
    db.refresh(lead)
    return lead


def assign_lead(db: Session, lead: Lead, counselor_user_id: int | None, admin_user: User):
    previous_user_id = lead.assigned_to_user_id
    counselor = None
    if counselor_user_id is not None:
        counselor = db.get(User, counselor_user_id)
        if not counselor or counselor.role != "COUNSELOR" or not counselor.active:
            raise HTTPException(status_code=400, detail="Choose an active counselor account.")

    if previous_user_id == counselor_user_id:
        return lead

    lead.assigned_to_user_id = counselor_user_id
    lead.assigned_at = datetime.now(timezone.utc) if counselor_user_id is not None else None
    new_name = counselor.display_name if counselor else "Unassigned"
    db.add(
        LeadActivity(
            lead_id=lead.id,
            user_id=admin_user.id,
            activity_type="ASSIGNMENT",
            channel="SYSTEM",
            notes=f"Lead assignment changed to {new_name}.",
        )
    )
    db.commit()
    db.refresh(lead)
    return lead


def add_lead_activity(
    db: Session,
    lead: Lead,
    user: User,
    activity_type: str,
    campaign_name: str | None,
    notes: str | None,
):
    normalized = activity_type.strip().upper()
    if normalized not in VALID_ACTIVITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Activity type must be one of: {', '.join(VALID_ACTIVITY_TYPES)}.",
        )

    if normalized in {"EMAIL_CAMPAIGN", "WHATSAPP_CAMPAIGN"} and not (campaign_name or "").strip():
        raise HTTPException(status_code=400, detail="Campaign name is required for email/WhatsApp activity.")

    channel_map = {
        "EMAIL_CAMPAIGN": "EMAIL",
        "WHATSAPP_CAMPAIGN": "WHATSAPP",
        "CALL": "CALL",
        "NOTE": "NOTE",
    }
    activity = LeadActivity(
        lead_id=lead.id,
        user_id=user.id,
        activity_type=normalized,
        channel=channel_map[normalized],
        campaign_name=(campaign_name or "").strip() or None,
        notes=(notes or "").strip() or None,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity
