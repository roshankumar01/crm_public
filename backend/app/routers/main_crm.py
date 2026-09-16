import re
import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthSession, Learner, MainCrmActivity, MainCrmLead, UploadBatch, User
from app.services.auth import get_current_user, hash_password, require_admin
from app.services.customer_identity import customer_is_registered, mark_customer_converted, resolve_customer
from app.services.importers.common import clean, dataframe_row_to_dict, parse_date, read_upload, require_columns

router = APIRouter(prefix="/crm/leads", tags=["Main CRM"])

SOURCE_CATEGORIES = {"INFO_EMAIL_LEADS", "LIVE_ONLINE_LEADS", "DIRECT_CALLS", "CAMPAIGN_REPLIES", "CAMPAIGN_DATA"}
REQUIRED_COLUMNS = {
    "INFO_EMAIL_LEADS": {"fullname", "email", "phonenumber", "source", "course"},
    "LIVE_ONLINE_LEADS": {"fullname", "email", "phonenumber", "whatsappnumber", "source", "course", "regions", "counsilorname", "country"},
    "DIRECT_CALLS": {"date", "email", "phonenumber", "course"},
    "CAMPAIGN_REPLIES": {"date", "email", "campaigntype", "course", "fulluserreply", "campaignname", "campaigndescription"},
    "CAMPAIGN_DATA": {"date", "email", "campaigntype", "campaignname", "campaigndescription", "coursecampaign"},
}


class StatusUpdate(BaseModel):
    status: str


class AssignmentUpdate(BaseModel):
    counselor_user_id: int | None = None


class CounselorCreate(BaseModel):
    username: str
    display_name: str
    email: str
    country: str | None = None
    region: str | None = None
    password: str


class CounselorUpdate(BaseModel):
    display_name: str
    email: str
    country: str | None = None
    region: str | None = None
    password: str | None = None


def normalize_email(value):
    value = clean(value)
    return value.lower() if value else None


def normalize_phone(value):
    value = clean(value)
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits[-10:] if len(digits) >= 10 else digits or None


def row_value(row, *keys):
    for key in keys:
        value = clean(row.get(key))
        if value is not None:
            return value
    return None


def lead_dict(lead, counselor=None):
    return {
        "id": lead.id, "customer_id": lead.customer_id, "full_name": lead.full_name, "email": lead.email,
        "phone_number": lead.phone_number, "whatsapp_number": lead.whatsapp_number,
        "source_category": lead.source_category, "source": lead.source, "course": lead.course,
        "region": lead.region, "country": lead.country, "age": lead.age, "status_of_lead": lead.status_of_lead,
        "assigned_to_user_id": lead.assigned_to_user_id,
        "counselor": counselor.display_name if counselor else None,
        "counselor_email": counselor.email if counselor else None,
        "sales_owner": lead.sales_owner, "notes": lead.notes,
        "matched_learner_number": lead.matched_learner_number,
        "created_at": lead.created_at, "updated_at": lead.updated_at,
    }


def accessible_lead(db, lead_id, user):
    lead = db.get(MainCrmLead, lead_id)
    if not lead or (user.role != "ADMIN" and lead.assigned_to_user_id != user.id):
        raise HTTPException(status_code=404, detail="Lead not found.")
    return lead


def new_upload_number(db):
    while True:
        value = f"CRM-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(2).upper()}"
        if not db.scalar(select(UploadBatch).where(UploadBatch.unique_number == value)):
            return value


def counselor_dict(user):
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "email": user.email, "country": user.country, "region": user.region, "active": user.active}


@router.get("/counselor-mapping")
def list_counselor_mapping(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.execute(select(User).where(User.role == "COUNSELOR").order_by(User.display_name)).scalars().all()
    return [counselor_dict(user) for user in users]


@router.post("/counselor-mapping")
def create_counselor(payload: CounselorCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    if not username or db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=400, detail="That username is already used or invalid.")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must contain at least 8 characters.")
    user = User(username=username, display_name=payload.display_name.strip(), email=payload.email.strip().lower(), country=clean(payload.country), region=clean(payload.region), password_hash=hash_password(payload.password), role="COUNSELOR", active=True)
    db.add(user); db.commit(); db.refresh(user)
    return counselor_dict(user)


@router.patch("/counselor-mapping/{user_id}")
def update_counselor(user_id: int, payload: CounselorUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user or user.role != "COUNSELOR":
        raise HTTPException(status_code=404, detail="Counselor not found.")
    user.display_name = payload.display_name.strip(); user.email = payload.email.strip().lower(); user.country = clean(payload.country); user.region = clean(payload.region)
    if payload.password:
        if len(payload.password) < 8:
            raise HTTPException(status_code=400, detail="Password must contain at least 8 characters.")
        user.password_hash = hash_password(payload.password)
        db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit(); db.refresh(user)
    return counselor_dict(user)


@router.get("")
def list_leads(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(MainCrmLead, User).outerjoin(User, MainCrmLead.assigned_to_user_id == User.id)
    if current_user.role != "ADMIN":
        query = query.where(MainCrmLead.assigned_to_user_id == current_user.id)
    rows = db.execute(query.order_by(MainCrmLead.updated_at.desc(), MainCrmLead.id.desc())).all()
    return [lead_dict(lead, counselor) for lead, counselor in rows]


def activity_dict(activity, lead=None):
    return {
        "id": activity.id, "lead_id": activity.lead_id,
        "lead_name": lead.full_name if lead else None, "lead_email": lead.email if lead else None,
        "activity_type": activity.activity_type, "activity_date": activity.activity_date,
        "channel": activity.channel, "campaign_name": activity.campaign_name,
        "campaign_description": activity.campaign_description, "course": activity.course,
        "full_user_reply": activity.full_user_reply, "notes": activity.notes,
        "raw_data": activity.raw_data, "created_at": activity.created_at,
    }


@router.get("/campaign-activities")
def list_campaign_activities(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(MainCrmActivity, MainCrmLead).join(MainCrmLead, MainCrmActivity.lead_id == MainCrmLead.id).where(
        MainCrmActivity.activity_type.in_(["CAMPAIGN_SENT", "CAMPAIGN_REPLY"])
    )
    if current_user.role != "ADMIN":
        query = query.where(MainCrmLead.assigned_to_user_id == current_user.id)
    rows = db.execute(query.order_by(MainCrmActivity.activity_date.desc(), MainCrmActivity.id.desc())).all()
    return [activity_dict(activity, lead) for activity, lead in rows]


@router.get("/detail/{lead_id}")
def get_main_crm_lead(lead_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = accessible_lead(db, lead_id, current_user)
    counselor = db.get(User, lead.assigned_to_user_id) if lead.assigned_to_user_id else None
    activities = db.execute(select(MainCrmActivity).where(MainCrmActivity.lead_id == lead.id).order_by(
        MainCrmActivity.activity_date.desc(), MainCrmActivity.id.desc()
    )).scalars().all()
    return {"lead": lead_dict(lead, counselor), "activities": [activity_dict(item) for item in activities]}


@router.get("/uploads")
def list_crm_uploads(admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(UploadBatch).where(UploadBatch.import_type.like("MAIN_CRM_%"))
        .order_by(UploadBatch.uploaded_at.desc(), UploadBatch.id.desc())
    ).scalars().all()
    return [{
        "id": item.id, "unique_number": item.unique_number, "filename": item.filename,
        "source_category": item.import_type.removeprefix("MAIN_CRM_"), "status": item.status,
        "rows_total": item.rows_total, "rows_imported": item.rows_imported,
        "rows_skipped": item.rows_skipped, "uploaded_at": item.uploaded_at,
    } for item in rows]


@router.post("/upload")
def upload_leads(
    source_category: Annotated[str, Form()], file: Annotated[UploadFile, File()],
    upload_mode: Annotated[str, Form()] = "CREATE",
    unique_number: Annotated[str | None, Form()] = None,
    admin_user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    category = source_category.strip().upper()
    if category not in SOURCE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid lead source category.")
    mode = upload_mode.strip().upper()
    if mode == "UPDATE":
        if not unique_number:
            raise HTTPException(status_code=400, detail="Choose the upload number to update.")
        batch = db.scalar(select(UploadBatch).where(UploadBatch.unique_number == unique_number, UploadBatch.import_type.like("MAIN_CRM_%")))
        if not batch:
            raise HTTPException(status_code=404, detail="Upload number not found.")
        db.execute(delete(MainCrmActivity).where(MainCrmActivity.upload_batch_id == batch.id))
        has_other_activity = select(MainCrmActivity.id).where(MainCrmActivity.lead_id == MainCrmLead.id).exists()
        db.execute(delete(MainCrmLead).where(MainCrmLead.upload_batch_id == batch.id, ~has_other_activity))
        batch.import_type = f"MAIN_CRM_{category}"; batch.filename = file.filename or "unknown"
        batch.status = "PROCESSING"; batch.rows_total = 0; batch.rows_imported = 0; batch.rows_skipped = 0
        batch.error_message = None; batch.uploaded_at = datetime.now(timezone.utc)
        db.flush()
    elif mode == "CREATE":
        batch = UploadBatch(import_type=f"MAIN_CRM_{category}", unique_number=new_upload_number(db), filename=file.filename or "unknown", status="PROCESSING")
        db.add(batch); db.commit(); db.refresh(batch)
    else:
        raise HTTPException(status_code=400, detail="Upload mode must be CREATE or UPDATE.")
    try:
        df = read_upload(file); batch.rows_total = len(df)
        if category == "DIRECT_CALLS" and "fullname" not in df.columns and "fullnmae" not in df.columns:
            raise ValueError("Direct calls file is missing required column: full_name")
        require_columns(df, REQUIRED_COLUMNS[category], category.replace("_", " ").title())
        imported = skipped = 0
        counselors = db.execute(select(User).where(User.role == "COUNSELOR", User.active.is_(True))).scalars().all()
        by_email = {normalize_email(u.email): u for u in counselors if u.email}
        by_name = {u.display_name.strip().lower(): u for u in counselors}
        learners = db.execute(select(Learner)).scalars().all()
        learners_by_email = {normalize_email(item.email_id): item for item in learners if item.email_id}
        learners_by_phone = {normalize_phone(item.contact_number): item for item in learners if item.contact_number}
        for _, row in df.iterrows():
            email = normalize_email(row.get("email")); phone = normalize_phone(row_value(row, "phonenumber", "phone"))
            if not email and not phone:
                skipped += 1; continue
            customer = resolve_customer(db, row_value(row, "fullname", "fullnmae"), clean(row.get("email")), row_value(row, "phonenumber", "phone"))
            match_conditions = [MainCrmLead.customer_id == customer.id]
            if email: match_conditions.append(MainCrmLead.normalized_email == email)
            if phone: match_conditions.append(MainCrmLead.normalized_phone == phone)
            lead = db.scalar(select(MainCrmLead).where(or_(*match_conditions)).order_by(MainCrmLead.id))
            counselor_email = normalize_email(row_value(row, "counsiloremail", "counseloremail"))
            counselor_name = (row_value(row, "counselor", "counsilor", "counselorname", "counsilorname") or "").lower()
            counselor = by_email.get(counselor_email) or by_name.get(counselor_name)
            learner = learners_by_email.get(email) if email else None
            if not learner and phone: learner = learners_by_phone.get(phone)
            course = row_value(row, "course", "coursecampaign")
            values = {
                "full_name": row_value(row, "fullname", "fullnmae") or (lead.full_name if lead else "Unknown"), "email": clean(row.get("email")),
                "customer_id": customer.id,
                "normalized_email": email, "phone_number": row_value(row, "phonenumber", "phone"),
                "normalized_phone": phone, "whatsapp_number": row_value(row, "whatsappnumber", "whatsappno"),
                "source_category": category, "source": clean(row.get("source")) or category.replace("_", " ").title(), "course": course,
                "region": row_value(row, "regions", "region", "countryregion"), "country": clean(row.get("country")),
                "status_of_lead": (row_value(row, "statusoflead", "status") or (lead.status_of_lead if lead else "NEW")).upper().replace(" ", "_"),
                "assigned_to_user_id": counselor.id if counselor else (lead.assigned_to_user_id if lead else None), "sales_owner": clean(row.get("salesowner")),
                "notes": row_value(row, "note", "notes", "comment"),
                "matched_learner_number": learner.learner_number if learner else None, "upload_batch_id": batch.id,
            }
            try: values["age"] = int(float(row.get("age"))) if clean(row.get("age")) else None
            except (TypeError, ValueError): values["age"] = None
            if lead:
                for key, value in values.items():
                    if category in {"CAMPAIGN_REPLIES", "CAMPAIGN_DATA"} and key in {"source_category", "source", "upload_batch_id"}:
                        continue
                    if category in {"INFO_EMAIL_LEADS", "LIVE_ONLINE_LEADS", "DIRECT_CALLS"} or value is not None:
                        setattr(lead, key, value)
            else:
                lead = MainCrmLead(**values); db.add(lead)
            db.flush()
            if customer_is_registered(db, customer.id):
                mark_customer_converted(db, customer.id)
                lead.status_of_lead = "CONVERTED"
            activity_type = {"INFO_EMAIL_LEADS": "ENQUIRY", "LIVE_ONLINE_LEADS": "ENQUIRY", "DIRECT_CALLS": "DIRECT_CALL", "CAMPAIGN_REPLIES": "CAMPAIGN_REPLY", "CAMPAIGN_DATA": "CAMPAIGN_SENT"}[category]
            db.add(MainCrmActivity(
                lead_id=lead.id, upload_batch_id=batch.id, activity_type=activity_type,
                activity_date=parse_date(row.get("date")), channel=row_value(row, "campaigntype", "calltype", "source"),
                campaign_name=clean(row.get("campaignname")), campaign_description=clean(row.get("campaigndescription")),
                course=course, full_user_reply=clean(row.get("fulluserreply")),
                notes=row_value(row, "comment", "note", "notes"), raw_data=dataframe_row_to_dict(row),
            ))
            imported += 1
        batch.rows_imported = imported; batch.rows_skipped = skipped; batch.status = "COMPLETED"
        db.commit()
        return {"unique_number": batch.unique_number, "rows_total": batch.rows_total, "rows_imported": imported, "rows_skipped": skipped}
    except Exception as exc:
        db.rollback(); failed = db.get(UploadBatch, batch.id)
        if failed:
            failed.status = "FAILED"; failed.error_message = str(exc); db.commit()
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{lead_id}/status")
def update_status(lead_id: int, payload: StatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = accessible_lead(db, lead_id, current_user)
    lead.status_of_lead = payload.status.strip().upper(); lead.updated_at = datetime.now(timezone.utc)
    db.commit(); return {"id": lead.id, "status_of_lead": lead.status_of_lead}


@router.patch("/{lead_id}/assignment")
def update_assignment(lead_id: int, payload: AssignmentUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    lead = accessible_lead(db, lead_id, admin)
    counselor = db.get(User, payload.counselor_user_id) if payload.counselor_user_id else None
    if counselor and (counselor.role != "COUNSELOR" or not counselor.active):
        raise HTTPException(status_code=400, detail="Invalid counselor.")
    lead.assigned_to_user_id = counselor.id if counselor else None
    if counselor and (counselor.region or counselor.country):
        lead.region = counselor.region or counselor.country
    lead.updated_at = datetime.now(timezone.utc)
    db.commit(); return lead_dict(lead, counselor)
