from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Lead, LeadActivity, User
from app.services.lead_workflow import sync_opportunity_leads
from app.services.opportunities import SECTION_CONFIG, section_key
from app.services.date_filters import period_condition


def scoped_leads(db: Session, current_user: User, period: str = "all"):
    """Full rows are reserved for the explicit Excel export."""
    sync_opportunity_leads(db)
    query = select(Lead).where(Lead.is_active.is_(True))
    query = query.where(*period_condition(Lead.created_at, period))
    if current_user.role != "ADMIN":
        query = query.where(Lead.assigned_to_user_id == current_user.id)
    return db.scalars(query.order_by(Lead.created_at.desc())).all()


def build_lead_analytics(db: Session, current_user: User, period: str = "all"):
    """Aggregate in SQL so dashboards do not materialize every lead/activity."""
    sync_opportunity_leads(db)
    scope = [Lead.is_active.is_(True)]
    scope.extend(period_condition(Lead.created_at, period))
    if current_user.role != "ADMIN":
        scope.append(Lead.assigned_to_user_id == current_user.id)
    grouped = db.execute(select(
        Lead.status, Lead.target_code, Lead.opportunity_key, Lead.stage, Lead.assigned_to_user_id, Lead.is_active,
        func.count(Lead.id)
    ).where(*scope).group_by(Lead.status, Lead.target_code, Lead.opportunity_key, Lead.stage, Lead.assigned_to_user_id, Lead.is_active)).all()
    status_counts = Counter()
    target = defaultdict(Counter)
    counselor = defaultdict(Counter)
    total = assigned = active_rule_leads = 0
    for status, target_code, opportunity_key, stage, owner, is_active, count in grouped:
        total += count
        status_counts[status] += count
        section = section_key(opportunity_key, stage)
        target[(target_code, section)][status] += count
        target[(target_code, section)]["total"] += count
        if owner is not None:
            assigned += count
            counselor[owner][status] += count
            counselor[owner]["total"] += count
        if is_active:
            active_rule_leads += count
    ids = list(counselor)
    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    counselor_rows = []
    for owner, counts in counselor.items():
        count = counts["total"]
        counselor_rows.append({
            "counselor_id": owner,
            "counselor_name": users[owner].display_name if owner in users else f"User {owner}",
            "total": count, "new": counts["NEW"], "in_contact": counts["IN_CONTACT"],
            "rejected": counts["REJECTED"], "converted": counts["CONVERTED"],
            "conversion_rate": round(counts["CONVERTED"] / count * 100, 1) if count else 0,
        })
    counselor_rows.sort(key=lambda item: (-item["conversion_rate"], -item["total"], item["counselor_name"]))
    target_rows = [{"target_code": code, "section_key": section,
                    "target_name": SECTION_CONFIG.get(section, (code, code))[1], "total": counts["total"],
                    "new": counts["NEW"], "in_contact": counts["IN_CONTACT"],
                    "rejected": counts["REJECTED"], "converted": counts["CONVERTED"]}
                   for (code, section), counts in sorted(target.items())]

    activity_scope = [Lead.is_active.is_(True), *period_condition(Lead.created_at, period)] if current_user.role == "ADMIN" else [Lead.is_active.is_(True), *period_condition(Lead.created_at, period), Lead.assigned_to_user_id == current_user.id]
    activity_counts = Counter(dict(db.execute(select(LeadActivity.activity_type, func.count(LeadActivity.id))
        .join(Lead, LeadActivity.lead_id == Lead.id).where(*activity_scope)
        .group_by(LeadActivity.activity_type)).all()))

    open_scope = [*scope, Lead.status.not_in(("CONVERTED", "REJECTED"))]
    today = date.today()
    aging = {
        "0_7_days": db.scalar(select(func.count(Lead.id)).where(*open_scope, Lead.trigger_date >= today - timedelta(days=7))) or 0,
        "8_30_days": db.scalar(select(func.count(Lead.id)).where(*open_scope, Lead.trigger_date < today - timedelta(days=7), Lead.trigger_date >= today - timedelta(days=30))) or 0,
        "over_30_days": db.scalar(select(func.count(Lead.id)).where(*open_scope, Lead.trigger_date < today - timedelta(days=30))) or 0,
        "unknown": db.scalar(select(func.count(Lead.id)).where(*open_scope, Lead.trigger_date.is_(None))) or 0,
    }
    unique_learners = db.scalar(select(func.count(func.distinct(Lead.customer_id))).where(*scope)) or 0
    converted = status_counts["CONVERTED"]
    return {
        "scope": "ALL" if current_user.role == "ADMIN" else "MY_LEADS",
        "summary": {
            "total_leads": total, "unique_learners": unique_learners,
            "active_rule_leads": active_rule_leads, "assigned": assigned,
            "unassigned": total - assigned,
            "new": status_counts["NEW"], "in_contact": status_counts["IN_CONTACT"],
            "rejected": status_counts["REJECTED"], "converted": converted,
            "conversion_rate": round(converted / total * 100, 1) if total else 0,
            "email_campaign_activities": activity_counts["EMAIL_CAMPAIGN"],
            "whatsapp_campaign_activities": activity_counts["WHATSAPP_CAMPAIGN"],
            "calls": activity_counts["CALL"],
        },
        "counselor_breakdown": counselor_rows,
        "target_breakdown": target_rows,
        "aging": aging,
    }
