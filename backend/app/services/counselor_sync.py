"""Carry Main CRM ownership across contact-linked learner and upsell records."""
from sqlalchemy import case, func, select, update

from app.models import Lead, MainCrmLead, User


def main_counselors(db, customer_ids=None):
    """One query for a page of contacts; newest assigned Main CRM record wins."""
    conditions = [MainCrmLead.customer_id.is_not(None), User.active.is_(True), User.role == "COUNSELOR"]
    if customer_ids is not None:
        ids = {value for value in customer_ids if value is not None}
        if not ids:
            return {}
        conditions.append(MainCrmLead.customer_id.in_(ids))
    ranked = select(
        MainCrmLead.customer_id.label("customer_id"), User.id.label("user_id"),
        User.display_name.label("name"), User.email.label("email"),
        func.row_number().over(partition_by=MainCrmLead.customer_id,
            order_by=(MainCrmLead.updated_at.desc(), MainCrmLead.id.desc())).label("rank"),
    ).join(User, MainCrmLead.assigned_to_user_id == User.id).where(*conditions).subquery()
    return {row.customer_id: {"assigned_to_user_id": row.user_id, "assigned_to_name": row.name,
                             "assigned_to_email": row.email, "assignment_source": "MAIN_CRM"}
            for row in db.execute(select(ranked).where(ranked.c.rank == 1))}


def counselor_fields(owners, customer_id):
    return owners.get(customer_id, {"assigned_to_user_id": None, "assigned_to_name": None,
                                   "assigned_to_email": None, "assignment_source": None})


def sync_main_counselors(db, customer_ids=None):
    """Set-based reconciliation on imports/assignment changes, never per list row.

    Preserve manually assigned, unmatched leads and the lead's business update date.
    Only an assignment previously inherited from Main CRM can be cleared.
    The caller owns the transaction.
    """
    db.flush()
    owner = select(MainCrmLead.assigned_to_user_id).join(User, MainCrmLead.assigned_to_user_id == User.id).where(
        MainCrmLead.customer_id == Lead.customer_id, User.active.is_(True), User.role == "COUNSELOR",
    ).order_by(MainCrmLead.updated_at.desc(), MainCrmLead.id.desc()).limit(1).correlate(Lead).scalar_subquery()
    conditions = [Lead.customer_id.is_not(None),
                  (owner.is_not(None) | Lead.counselor_from_main.is_(True)),
                  (Lead.assigned_to_user_id.is_distinct_from(owner) |
                   Lead.counselor_from_main.is_distinct_from(owner.is_not(None)))]
    if customer_ids is not None:
        ids = {value for value in customer_ids if value is not None}
        if not ids:
            return
        conditions.append(Lead.customer_id.in_(ids))
    db.execute(update(Lead).where(*conditions).values(
        assigned_to_user_id=owner, counselor_from_main=owner.is_not(None),
        assigned_at=case((owner.is_not(None), func.now()), else_=None), updated_at=Lead.updated_at,
    ), execution_options={"synchronize_session": False})
    db.expire_all()
