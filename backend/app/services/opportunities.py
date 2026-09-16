from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Lead, Learner, LearnerCourseRecord, MarketingCampaign, User
from app.services.course_rules import build_learner_opportunities
from app.services.lead_workflow import sync_opportunity_leads

SECTION_CONFIG = {
    "IDP_ENTRY": {
        "title": "IDP Entry",
        "target_code": "IDP",
        "description": "Learners who completed IGC and have not yet entered ID1, ID2 or ID3.",
    },
    "ID1": {
        "title": "ID1 Opportunities",
        "target_code": "ID1",
        "description": "Learners who completed another IDP course but have not yet entered ID1.",
    },
    "ID2": {
        "title": "ID2 Opportunities",
        "target_code": "ID2",
        "description": "Learners who completed another IDP course but have not yet entered ID2.",
    },
    "ID3": {
        "title": "ID3 Opportunities",
        "target_code": "ID3",
        "description": "Learners who completed another IDP course but have not yet entered ID3.",
    },
}
SECTION_ORDER = ("IDP_ENTRY", "ID1", "ID2", "ID3")


def load_history_by_learner(db: Session):
    rows = db.execute(
        select(LearnerCourseRecord, Course)
        .join(Course, LearnerCourseRecord.course_id == Course.id)
        .order_by(
            LearnerCourseRecord.learner_number,
            LearnerCourseRecord.event_date,
            LearnerCourseRecord.id,
        )
    ).all()

    grouped = defaultdict(list)
    for record, course in rows:
        grouped[record.learner_number].append((record, course))
    return grouped


def get_all_opportunities(db: Session, current_user: User | None = None):
    sync_opportunity_leads(db)

    learners = db.execute(select(Learner).order_by(Learner.name)).scalars().all()
    history_by_learner = load_history_by_learner(db)
    leads_by_section = {key: [] for key in SECTION_ORDER}
    today = date.today()

    crm_leads = db.execute(select(Lead).where(Lead.is_active.is_(True))).scalars().all()
    crm_by_key = {(lead.learner_number, lead.opportunity_key): lead for lead in crm_leads}

    counselor_ids = {lead.assigned_to_user_id for lead in crm_leads if lead.assigned_to_user_id}
    counselors = {}
    if counselor_ids:
        counselors = {
            user.id: user
            for user in db.execute(select(User).where(User.id.in_(counselor_ids))).scalars().all()
        }

    campaign_rows = db.execute(
        select(MarketingCampaign)
        .order_by(MarketingCampaign.created_at.desc(), MarketingCampaign.id.desc())
    ).scalars().all()
    latest_campaign = {}
    for campaign in campaign_rows:
        latest_campaign.setdefault(campaign.learner_number, campaign)

    for learner in learners:
        history_rows = history_by_learner.get(learner.learner_number, [])
        for opportunity in build_learner_opportunities(history_rows):
            crm = crm_by_key.get((learner.learner_number, opportunity["key"]))
            if not crm:
                continue
            if current_user and current_user.role != "ADMIN" and crm.assigned_to_user_id != current_user.id:
                continue

            trigger_date = opportunity.get("trigger_date")
            days_since = (today - trigger_date).days if trigger_date else None
            counselor = counselors.get(crm.assigned_to_user_id)
            campaign = latest_campaign.get(learner.learner_number)
            leads_by_section[opportunity["key"]].append({
                "lead_id": crm.id,
                "learner_number": learner.learner_number,
                "name": learner.name,
                "email_id": learner.email_id,
                "contact_number": learner.contact_number,
                "nationality": learner.nationality,
                "last_activity_date": learner.last_activity_date,
                "target_code": opportunity["target_code"],
                "target_name": opportunity["target_name"],
                "opportunity_type": opportunity["opportunity_type"],
                "trigger_courses": opportunity["trigger_courses"],
                "trigger_date": trigger_date,
                "days_since_trigger": days_since,
                "reason": opportunity["reason"],
                "status": crm.status,
                "assigned_to_user_id": crm.assigned_to_user_id,
                "assigned_to_name": counselor.display_name if counselor else None,
                "assigned_at": crm.assigned_at,
                "status_updated_at": crm.status_updated_at,
                "latest_campaign": ({
                    "marketing_type": campaign.marketing_type,
                    "campaign_name": campaign.campaign_name,
                    "created_at": campaign.created_at,
                } if campaign else None),
            })

    for key in SECTION_ORDER:
        leads_by_section[key].sort(
            key=lambda item: (
                item["trigger_date"] is None,
                item["trigger_date"] or date.max,
                item["name"],
            )
        )

    sections = []
    for key in SECTION_ORDER:
        config = SECTION_CONFIG[key]
        leads = leads_by_section[key]
        sections.append({
            "key": key,
            "title": config["title"],
            "target_code": config["target_code"],
            "description": config["description"],
            "count": len(leads),
            "leads": leads,
        })

    unique_learners = {lead["learner_number"] for section in sections for lead in section["leads"]}
    all_visible_leads = [lead for section in sections for lead in section["leads"]]
    return {
        "summary": {
            "unique_learners": len(unique_learners),
            "total_opportunities": sum(section["count"] for section in sections),
            "idp_entry": len(leads_by_section["IDP_ENTRY"]),
            "id1": len(leads_by_section["ID1"]),
            "id2": len(leads_by_section["ID2"]),
            "id3": len(leads_by_section["ID3"]),
            "new": sum(1 for lead in all_visible_leads if lead["status"] == "NEW"),
            "in_contact": sum(1 for lead in all_visible_leads if lead["status"] == "IN_CONTACT"),
            "converted": sum(1 for lead in all_visible_leads if lead["status"] == "CONVERTED"),
            "rejected": sum(1 for lead in all_visible_leads if lead["status"] == "REJECTED"),
            "unassigned": sum(1 for lead in all_visible_leads if lead["assigned_to_user_id"] is None),
        },
        "sections": sections,
    }
