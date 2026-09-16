from collections import Counter
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lead, LeadActivity, MarketingCampaign, User
from app.services.lead_workflow import sync_opportunity_leads


def scoped_leads(db: Session, current_user: User):
    sync_opportunity_leads(db)
    query = select(Lead)
    if current_user.role != "ADMIN":
        query = query.where(Lead.assigned_to_user_id == current_user.id)
    return db.execute(query.order_by(Lead.created_at.desc())).scalars().all()


def build_lead_analytics(db: Session, current_user: User):
    leads = scoped_leads(db, current_user)
    lead_ids = [lead.id for lead in leads]
    assigned_user_ids = {lead.assigned_to_user_id for lead in leads if lead.assigned_to_user_id}

    users = {}
    if assigned_user_ids:
        users = {
            user.id: user
            for user in db.execute(select(User).where(User.id.in_(assigned_user_ids))).scalars().all()
        }

    activities = []
    if lead_ids:
        activities = db.execute(
            select(LeadActivity).where(LeadActivity.lead_id.in_(lead_ids))
        ).scalars().all()

    status_counts = Counter(lead.status for lead in leads)
    target_counts = Counter(lead.target_code for lead in leads)
    activity_counts = Counter(activity.activity_type for activity in activities)
    total = len(leads)
    converted = status_counts["CONVERTED"]
    active_rule_leads = sum(1 for lead in leads if lead.is_active)

    counselor_rows = []
    counselor_ids = sorted({lead.assigned_to_user_id for lead in leads if lead.assigned_to_user_id})
    for counselor_id in counselor_ids:
        counselor_leads = [lead for lead in leads if lead.assigned_to_user_id == counselor_id]
        counts = Counter(lead.status for lead in counselor_leads)
        counselor = users.get(counselor_id)
        counselor_total = len(counselor_leads)
        counselor_rows.append({
            "counselor_id": counselor_id,
            "counselor_name": counselor.display_name if counselor else f"User {counselor_id}",
            "total": counselor_total,
            "new": counts["NEW"],
            "in_contact": counts["IN_CONTACT"],
            "rejected": counts["REJECTED"],
            "converted": counts["CONVERTED"],
            "conversion_rate": round((counts["CONVERTED"] / counselor_total * 100), 1) if counselor_total else 0,
        })

    target_rows = []
    for target in ("IDP", "ID1", "ID2", "ID3"):
        target_leads = [lead for lead in leads if lead.target_code == target]
        counts = Counter(lead.status for lead in target_leads)
        target_rows.append({
            "target_code": target,
            "total": target_counts[target],
            "new": counts["NEW"],
            "in_contact": counts["IN_CONTACT"],
            "rejected": counts["REJECTED"],
            "converted": counts["CONVERTED"],
        })

    aging = {"0_7_days": 0, "8_30_days": 0, "over_30_days": 0, "unknown": 0}
    today = date.today()
    for lead in leads:
        if not lead.is_active or lead.status in {"CONVERTED", "REJECTED"}:
            continue
        if not lead.trigger_date:
            aging["unknown"] += 1
            continue
        age = max((today - lead.trigger_date).days, 0)
        if age <= 7:
            aging["0_7_days"] += 1
        elif age <= 30:
            aging["8_30_days"] += 1
        else:
            aging["over_30_days"] += 1

    return {
        "scope": "ALL" if current_user.role == "ADMIN" else "MY_LEADS",
        "summary": {
            "total_leads": total,
            "unique_learners": len({lead.learner_number for lead in leads}),
            "active_rule_leads": active_rule_leads,
            "assigned": sum(1 for lead in leads if lead.assigned_to_user_id is not None),
            "unassigned": sum(1 for lead in leads if lead.assigned_to_user_id is None),
            "new": status_counts["NEW"],
            "in_contact": status_counts["IN_CONTACT"],
            "rejected": status_counts["REJECTED"],
            "converted": converted,
            "conversion_rate": round((converted / total * 100), 1) if total else 0,
            "email_campaign_activities": activity_counts["EMAIL_CAMPAIGN"],
            "whatsapp_campaign_activities": activity_counts["WHATSAPP_CAMPAIGN"],
            "calls": activity_counts["CALL"],
        },
        "counselor_breakdown": counselor_rows,
        "target_breakdown": target_rows,
        "aging": aging,
    }
