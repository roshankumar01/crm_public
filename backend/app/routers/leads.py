from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lead, LeadActivity, Learner, MarketingCampaign, User
from app.services.auth import get_current_user, require_admin
from app.services.lead_workflow import (
    add_lead_activity,
    assign_lead,
    change_lead_status,
    get_accessible_lead,
    sync_opportunity_leads,
)

router = APIRouter(prefix="/leads", tags=["Leads"])


class StatusUpdate(BaseModel):
    status: str


class AssignmentUpdate(BaseModel):
    counselor_user_id: int | None = None


class ActivityCreate(BaseModel):
    activity_type: str
    campaign_name: str | None = None
    notes: str | None = None


@router.get("/counselors")
def get_counselors(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    counselors = db.execute(
        select(User)
        .where(User.role == "COUNSELOR", User.active.is_(True))
        .order_by(User.display_name)
    ).scalars().all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "country": user.country,
            "region": user.region,
        }
        for user in counselors
    ]


@router.get("")
def get_tracked_leads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sync_opportunity_leads(db)
    query = (
        select(Lead, Learner, User)
        .join(Learner, Lead.learner_number == Learner.learner_number)
        .outerjoin(User, Lead.assigned_to_user_id == User.id)
    )
    if current_user.role != "ADMIN":
        query = query.where(Lead.assigned_to_user_id == current_user.id)

    rows = db.execute(
        query.order_by(Lead.is_active.desc(), Lead.updated_at.desc(), Lead.id.desc())
    ).all()
    campaign_rows = db.execute(
        select(MarketingCampaign).order_by(MarketingCampaign.created_at.desc(), MarketingCampaign.id.desc())
    ).scalars().all()
    latest_campaign = {}
    for campaign in campaign_rows:
        latest_campaign.setdefault(campaign.learner_number, campaign)
    return [
        {
            "lead_id": lead.id,
            "learner_number": learner.learner_number,
            "name": learner.name,
            "email_id": learner.email_id,
            "contact_number": learner.contact_number,
            "target_code": lead.target_code,
            "opportunity_key": lead.opportunity_key,
            "trigger_date": lead.trigger_date,
            "status": lead.status,
            "is_active": lead.is_active,
            "assigned_to_user_id": lead.assigned_to_user_id,
            "assigned_to_name": counselor.display_name if counselor else None,
            "updated_at": lead.updated_at,
            "latest_campaign": ({
                "marketing_type": latest_campaign[learner.learner_number].marketing_type,
                "campaign_name": latest_campaign[learner.learner_number].campaign_name,
                "created_at": latest_campaign[learner.learner_number].created_at,
            } if learner.learner_number in latest_campaign else None),
        }
        for lead, learner, counselor in rows
    ]


@router.get("/{lead_id}")
def get_lead(
    lead_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sync_opportunity_leads(db)
    lead = get_accessible_lead(db, lead_id, current_user)
    learner = db.get(Learner, lead.learner_number)
    counselor = db.get(User, lead.assigned_to_user_id) if lead.assigned_to_user_id else None

    activity_rows = db.execute(
        select(LeadActivity, User)
        .outerjoin(User, LeadActivity.user_id == User.id)
        .where(LeadActivity.lead_id == lead.id)
        .order_by(LeadActivity.created_at.desc(), LeadActivity.id.desc())
    ).all()
    campaigns = db.execute(
        select(MarketingCampaign)
        .where(MarketingCampaign.learner_number == lead.learner_number)
        .order_by(MarketingCampaign.created_at.desc(), MarketingCampaign.id.desc())
    ).scalars().all()

    return {
        "lead": {
            "id": lead.id,
            "learner_number": lead.learner_number,
            "opportunity_key": lead.opportunity_key,
            "target_code": lead.target_code,
            "trigger_date": lead.trigger_date,
            "status": lead.status,
            "is_active": lead.is_active,
            "assigned_to_user_id": lead.assigned_to_user_id,
            "assigned_to_name": counselor.display_name if counselor else None,
            "assigned_at": lead.assigned_at,
            "status_updated_at": lead.status_updated_at,
            "created_at": lead.created_at,
            "updated_at": lead.updated_at,
        },
        "learner": {
            "learner_number": learner.learner_number,
            "name": learner.name,
            "email_id": learner.email_id,
            "contact_number": learner.contact_number,
            "nationality": learner.nationality,
            "last_activity_date": learner.last_activity_date,
        } if learner else None,
        "activities": [
            {
                "id": activity.id,
                "activity_type": activity.activity_type,
                "channel": activity.channel,
                "campaign_name": activity.campaign_name,
                "notes": activity.notes,
                "created_at": activity.created_at,
                "user_name": activity_user.display_name if activity_user else "System",
            }
            for activity, activity_user in activity_rows
        ],
        "campaigns": [
            {
                "id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "marketing_type": campaign.marketing_type,
                "created_at": campaign.created_at,
            }
            for campaign in campaigns
        ],
    }


@router.patch("/{lead_id}/status")
def update_status(
    lead_id: int,
    payload: StatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = get_accessible_lead(db, lead_id, current_user)
    updated = change_lead_status(db, lead, payload.status, current_user)
    return {"id": updated.id, "status": updated.status, "status_updated_at": updated.status_updated_at}


@router.patch("/{lead_id}/assignment")
def update_assignment(
    lead_id: int,
    payload: AssignmentUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    lead = get_accessible_lead(db, lead_id, admin_user)
    updated = assign_lead(db, lead, payload.counselor_user_id, admin_user)
    counselor = db.get(User, updated.assigned_to_user_id) if updated.assigned_to_user_id else None
    return {
        "id": updated.id,
        "assigned_to_user_id": updated.assigned_to_user_id,
        "assigned_to_name": counselor.display_name if counselor else None,
        "assigned_at": updated.assigned_at,
    }


@router.post("/{lead_id}/activities")
def create_activity(
    lead_id: int,
    payload: ActivityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = get_accessible_lead(db, lead_id, current_user)
    activity = add_lead_activity(
        db,
        lead,
        current_user,
        payload.activity_type,
        payload.campaign_name,
        payload.notes,
    )
    return {
        "id": activity.id,
        "activity_type": activity.activity_type,
        "channel": activity.channel,
        "campaign_name": activity.campaign_name,
        "notes": activity.notes,
        "created_at": activity.created_at,
        "user_name": current_user.display_name,
    }
