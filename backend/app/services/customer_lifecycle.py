"""A current, cross-workspace history for one linked customer."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Course, Lead, LeadActivity, Learner, LearnerCourseRecord,
    LearnersCrmEnrollment, LearnersCrmProfile, MainCrmActivity,
    MainCrmLead, MarketingCampaign, UploadBatch, UpsellCourseCase, User,
)


def customer_lifecycle(db: Session, customer_id: int | None, user: User):
    if customer_id is None:
        return {"customer_id": None, "events": []}

    events = []

    def add(kind, date, title, detail=None, status=None, href=None, key=None, fields=None, raw_data=None, source_label=None):
        events.append({
            "key": key or f"{kind}-{len(events)}", "kind": kind,
            "date": date.isoformat() if date else None,
            "title": title, "detail": detail, "status": status, "href": href,
            "fields": fields or {}, "raw_data": raw_data or {},
            "source_label": source_label,
        })

    main_query = select(MainCrmLead).where(MainCrmLead.customer_id == customer_id)
    if user.role != "ADMIN":
        main_query = main_query.where(MainCrmLead.assigned_to_user_id == user.id)
    main_leads = db.scalars(main_query.order_by(MainCrmLead.id)).all()
    if main_leads:
        by_id = {lead.id: lead for lead in main_leads}
        activities = db.scalars(select(MainCrmActivity).where(
            MainCrmActivity.lead_id.in_(by_id), MainCrmActivity.activity_type != "EDIT"
        ).order_by(MainCrmActivity.id)).all()
        with_activity = {activity.lead_id for activity in activities}
        for lead in main_leads:
            if lead.id not in with_activity:
                add("ENQUIRY", lead.created_at, "Enquiry received",
                    f"{lead.source or lead.source_category} · {lead.course or 'Course not provided'}",
                    lead.status_of_lead, f"/crm/leads/{lead.id}", f"lead-{lead.id}")
        labels = {
            "ENQUIRY": "Enquiry received", "DIRECT_CALL": "Phone enquiry",
            "CAMPAIGN_SENT": "Campaign sent", "CAMPAIGN_REPLY": "Campaign reply",
            "MIGRATION": "Old CRM record imported",
        }
        for activity in activities:
            lead = by_id[activity.lead_id]
            detail = activity.full_user_reply or activity.notes or activity.campaign_name or activity.course or lead.source
            kind = "MARKETING" if activity.activity_type in {"CAMPAIGN_SENT", "CAMPAIGN_REPLY"} else "ENQUIRY"
            add(kind, activity.activity_date or activity.created_at,
                labels.get(activity.activity_type, activity.activity_type.replace("_", " ").title()),
                detail, lead.status_of_lead, f"/crm/leads/{lead.id}", f"main-activity-{activity.id}",
                fields={"source": lead.source, "course": activity.course or lead.course,
                        "channel": activity.channel, "campaign": activity.campaign_name,
                        "message": activity.full_user_reply, "note": activity.notes},
                raw_data=activity.raw_data)

    profiles = db.scalars(select(LearnersCrmProfile).where(
        LearnersCrmProfile.customer_id == customer_id
    )).all()
    if profiles:
        profile_ids = {profile.id for profile in profiles}
        enrolments = db.scalars(select(LearnersCrmEnrollment).where(
            LearnersCrmEnrollment.learner_id.in_(profile_ids)
        ).order_by(LearnersCrmEnrollment.enrolment_id)).all()
        for enrolment in enrolments:
            link = f"/learners-crm/learners/{enrolment.learner_id}"
            detail = f"Enrolment {enrolment.enrolment_id}"
            add("ENROLMENT", enrolment.enrolment_date or enrolment.created_at,
                f"Enrolled in {enrolment.course_name}", detail,
                enrolment.completion_status, link, f"enrolment-{enrolment.enrolment_id}",
                fields={"enrolment_id": enrolment.enrolment_id,
                        "start_date": enrolment.start_date.isoformat() if enrolment.start_date else None,
                        "completion_date": enrolment.completion_date.isoformat() if enrolment.completion_date else None})
            if enrolment.completion_date and (enrolment.completion_status or "").strip().casefold() == "completed":
                add("COMPLETION", enrolment.completion_date, f"Completed {enrolment.course_name}",
                    detail, "Completed", link, f"completion-{enrolment.enrolment_id}",
                    fields={"enrolment_id": enrolment.enrolment_id})

    learners = db.scalars(select(Learner).where(Learner.customer_id == customer_id)).all()
    if learners:
        numbers = {learner.learner_number for learner in learners}
        result_rows = db.execute(select(LearnerCourseRecord, Course, UploadBatch.import_type).join(
            Course, Course.id == LearnerCourseRecord.course_id
        ).outerjoin(UploadBatch, UploadBatch.id == LearnerCourseRecord.upload_batch_id
        ).where(LearnerCourseRecord.learner_number.in_(numbers)).order_by(
            LearnerCourseRecord.event_date, LearnerCourseRecord.id
        )).all()
        for record, course, import_type in result_rows:
            result_type = import_type or course.program_code or course.code
            if result_type == "IDIP": result_type = "IDP"
            add("RESULT", record.event_date, course.name,
                f"Learner #{record.learner_number}", record.result or record.enrollment_status,
                f"/upsell/learners/{record.learner_number}" if user.role == "ADMIN" else None,
                f"result-{record.id}", fields=record.details, source_label=f"Result data {result_type}")
        campaigns = db.scalars(select(MarketingCampaign).where(
            MarketingCampaign.learner_number.in_(numbers)
        ).order_by(MarketingCampaign.id)).all()
        for campaign in campaigns:
            add("MARKETING", campaign.created_at, "Marketing campaign sent",
                f"{campaign.marketing_type}: {campaign.campaign_name}", None,
                f"/upsell/learners/{campaign.learner_number}" if user.role == "ADMIN" else None,
                f"campaign-{campaign.id}")


    opportunity_query = select(Lead).where(Lead.customer_id == customer_id)
    if user.role != "ADMIN":
        opportunity_query = opportunity_query.where(Lead.assigned_to_user_id == user.id)
    opportunities = db.scalars(opportunity_query.order_by(Lead.id)).all()
    if opportunities:
        by_id = {lead.id: lead for lead in opportunities}
        for lead in opportunities:
            add("UPSELL", lead.trigger_date or lead.created_at,
                f"Upsell opportunity: {lead.target_code}", lead.reason,
                lead.status, f"/upsell/leads/{lead.id}", f"opportunity-{lead.id}")
        activities = db.scalars(select(LeadActivity).where(LeadActivity.lead_id.in_(by_id)).order_by(
            LeadActivity.id
        )).all()
        for activity in activities:
            lead = by_id[activity.lead_id]
            add("UPSELL", activity.created_at,
                f"Upsell {activity.activity_type.replace('_', ' ').title()}",
                activity.notes or activity.campaign_name or lead.target_code,
                lead.status, f"/upsell/leads/{lead.id}",
                f"upsell-activity-{activity.id}")

    # Counselor-reported conversions are visible everywhere, separately from uploaded registrations.
    conversions = db.execute(select(UpsellCourseCase, User.display_name).outerjoin(User, User.id == UpsellCourseCase.counselor_id)
        .where(UpsellCourseCase.customer_id == customer_id, UpsellCourseCase.status == "CONVERTED")
        .order_by(UpsellCourseCase.converted_at.desc()).limit(100)).all()
    for conversion, counselor in conversions:
        add("UPSELL", conversion.converted_at, f"Course converted: {conversion.course_name}",
            "Counselor-reported conversion", "CONVERTED", f"/upsell/leads/{conversion.lead_id}",
            f"course-conversion-{conversion.id}", fields={"main_category": conversion.main_category,
                "sub_category": conversion.sub_category, "course": conversion.course_name, "counselor": counselor},
            source_label="Upsell course conversion")

    events.sort(key=lambda item: (item["date"] or "", item["key"]), reverse=True)
    return {"customer_id": customer_id, "events": events}
