from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, Lead, LeadActivity, Learner, MarketingCampaign, User
from app.services.auth import get_current_user
from app.services.lead_analytics import build_lead_analytics, scoped_leads
from app.services.opportunities import section_key

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/leads")
def get_lead_analytics(
    period: str = "all",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_lead_analytics(db, current_user, period)


@router.get("/leads/export")
def export_lead_analytics(
    opportunity_key: str | None = Query(default=None),
    period: str = "all",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analytics = build_lead_analytics(db, current_user, period)
    leads = scoped_leads(db, current_user, period)
    if opportunity_key:
        leads = [lead for lead in leads if section_key(lead.opportunity_key, lead.stage) == opportunity_key and lead.is_active]
    lead_ids = [lead.id for lead in leads]

    learners = {}
    learner_numbers = {lead.learner_number for lead in leads}
    if learner_numbers:
        learners = {
            learner.learner_number: learner
            for learner in db.execute(
                select(Learner).where(Learner.learner_number.in_(learner_numbers))
            ).scalars().all()
        }

    customer_ids = {lead.customer_id for lead in leads if lead.customer_id}
    customers = {customer.id: customer for customer in db.scalars(select(Customer).where(Customer.id.in_(customer_ids)))} if customer_ids else {}

    counselor_ids = {lead.assigned_to_user_id for lead in leads if lead.assigned_to_user_id}
    counselors = {}
    if counselor_ids:
        counselors = {
            user.id: user
            for user in db.execute(select(User).where(User.id.in_(counselor_ids))).scalars().all()
        }

    lead_rows = []
    for lead in leads:
        learner = learners.get(lead.learner_number)
        customer = customers.get(lead.customer_id)
        counselor = counselors.get(lead.assigned_to_user_id)
        lead_rows.append({
            "Lead ID": lead.id,
            "Learner Number": lead.learner_number,
            "Learner Name": customer.primary_name if customer else learner.name if learner else "",
            "Email": customer.primary_email if customer else learner.email_id if learner else "",
            "Phone": customer.primary_phone if customer else learner.contact_number if learner else "",
            "Opportunity": lead.opportunity_key,
            "Target": lead.target_code,
            "Trigger Date": lead.trigger_date,
            "CRM Status": lead.status,
            "Counselor": counselor.display_name if counselor else "Unassigned",
            "Current Rule Opportunity": "Yes" if lead.is_active else "No",
            "Assigned At": lead.assigned_at,
            "Status Updated At": lead.status_updated_at,
            "Lead Created At": lead.created_at,
        })

    activity_rows = []
    if lead_ids:
        rows = db.execute(
            select(LeadActivity, User, Lead)
            .join(Lead, LeadActivity.lead_id == Lead.id)
            .outerjoin(User, LeadActivity.user_id == User.id)
            .where(LeadActivity.lead_id.in_(lead_ids))
            .order_by(LeadActivity.created_at.desc())
        ).all()
        activity_rows = [
            {
                "Lead ID": activity.lead_id,
                "Learner Number": lead.learner_number,
                "Activity Type": activity.activity_type,
                "Channel": activity.channel,
                "Campaign Name": activity.campaign_name,
                "Notes": activity.notes,
                "User": user.display_name if user else "System",
                "Created At": activity.created_at,
            }
            for activity, user, lead in rows
        ]

    campaign_rows = []
    if learner_numbers:
        campaigns = db.execute(
            select(MarketingCampaign)
            .where(MarketingCampaign.learner_number.in_(learner_numbers))
            .order_by(MarketingCampaign.created_at.desc())
        ).scalars().all()
        campaign_rows = [
            {
                "Learner Number": campaign.learner_number,
                "Campaign Name": campaign.campaign_name,
                "Marketing Type": campaign.marketing_type,
                "Created At": campaign.created_at,
                "Upload Batch ID": campaign.upload_batch_id,
            }
            for campaign in campaigns
        ]

    if opportunity_key:
        summary_rows = [
            {"Metric": "Current opportunity", "Value": opportunity_key.replace("_", " ").title()},
            {"Metric": "Leads", "Value": len(leads)},
            {"Metric": "New", "Value": sum(lead.status == "NEW" for lead in leads)},
            {"Metric": "In contact", "Value": sum(lead.status == "IN_CONTACT" for lead in leads)},
            {"Metric": "Converted", "Value": sum(lead.status == "CONVERTED" for lead in leads)},
            {"Metric": "Rejected", "Value": sum(lead.status == "REJECTED" for lead in leads)},
        ]
    else:
        summary_rows = [
            {"Metric": key.replace("_", " ").title(), "Value": value}
            for key, value in analytics["summary"].items()
        ]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(lead_rows).to_excel(writer, sheet_name="Leads", index=False)
        pd.DataFrame(analytics["counselor_breakdown"]).to_excel(
            writer, sheet_name="Counselor Breakdown", index=False
        )
        pd.DataFrame(analytics["target_breakdown"]).to_excel(
            writer, sheet_name="Target Breakdown", index=False
        )
        pd.DataFrame(activity_rows).to_excel(writer, sheet_name="CRM Activities", index=False)
        pd.DataFrame(campaign_rows).to_excel(writer, sheet_name="Campaigns", index=False)
    output.seek(0)

    filename = f"{opportunity_key.lower()}-current-leads.xlsx" if opportunity_key else ("lead-analytics.xlsx" if current_user.role == "ADMIN" else "my-lead-analytics.xlsx")
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
