from datetime import datetime, timezone
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LearnersCrmEnrollment, LearnersCrmProfile, MainCrmLead, UploadBatch, User
from app.services.auth import get_current_user, require_admin
from app.services.customer_identity import mark_customer_converted, resolve_customer
from app.services.importers.common import clean, parse_date, read_upload, require_columns

router = APIRouter(prefix="/learners-crm", tags=["Learners CRM"])
REQUIRED_COLUMNS = {"enrolmentid", "learnername", "emailid", "coursename", "enrolmentdate", "startdate", "completiondate", "completionstatus"}


def normalize_email(value):
    value = clean(value)
    return value.lower() if value else None


def new_upload_number(db):
    while True:
        value = f"LCRM-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(2).upper()}"
        if not db.scalar(select(UploadBatch).where(UploadBatch.unique_number == value)):
            return value


@router.get("/overview")
def overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_learners = db.scalar(select(func.count()).select_from(LearnersCrmProfile)) or 0
    total_enrolments = db.scalar(select(func.count()).select_from(LearnersCrmEnrollment)) or 0
    completed = db.scalar(select(func.count()).select_from(LearnersCrmEnrollment).where(
        func.upper(LearnersCrmEnrollment.completion_status).in_(["COMPLETED", "COMPLETE", "PASSED", "PASS"])
    )) or 0
    active = db.scalar(select(func.count()).select_from(LearnersCrmEnrollment).where(
        func.upper(LearnersCrmEnrollment.completion_status).in_(["ACTIVE", "IN_PROGRESS", "IN PROGRESS", "STARTED"])
    )) or 0
    learner_emails = set(db.execute(select(LearnersCrmProfile.normalized_email)).scalars().all())
    enquiry_emails = set(db.execute(select(MainCrmLead.normalized_email).where(MainCrmLead.normalized_email.is_not(None))).scalars().all())
    return {"total_learners": total_learners, "total_enrolments": total_enrolments, "completed": completed, "active": active, "matched_enquiries": len(learner_emails & enquiry_emails)}


@router.get("/uploads")
def uploads(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(UploadBatch).where(UploadBatch.import_type == "LEARNERS_CRM").order_by(UploadBatch.uploaded_at.desc(), UploadBatch.id.desc())).scalars().all()
    return [{"id": row.id, "unique_number": row.unique_number, "filename": row.filename, "status": row.status, "rows_total": row.rows_total, "rows_imported": row.rows_imported, "rows_skipped": row.rows_skipped, "uploaded_at": row.uploaded_at} for row in rows]


@router.post("/upload")
def upload(
    file: Annotated[UploadFile, File()], upload_mode: Annotated[str, Form()] = "CREATE",
    unique_number: Annotated[str | None, Form()] = None,
    admin: User = Depends(require_admin), db: Session = Depends(get_db),
):
    mode = upload_mode.strip().upper()
    if mode == "UPDATE":
        if not unique_number:
            raise HTTPException(status_code=400, detail="Choose the learner upload to update.")
        batch = db.scalar(select(UploadBatch).where(UploadBatch.unique_number == unique_number, UploadBatch.import_type == "LEARNERS_CRM"))
        if not batch:
            raise HTTPException(status_code=404, detail="Learner upload number not found.")
        db.execute(delete(LearnersCrmEnrollment).where(LearnersCrmEnrollment.upload_batch_id == batch.id))
        batch.filename = file.filename or "unknown"; batch.status = "PROCESSING"
        batch.rows_total = 0; batch.rows_imported = 0; batch.rows_skipped = 0
        batch.error_message = None; batch.uploaded_at = datetime.now(timezone.utc); db.flush()
    elif mode == "CREATE":
        batch = UploadBatch(import_type="LEARNERS_CRM", unique_number=new_upload_number(db), filename=file.filename or "unknown", status="PROCESSING")
        db.add(batch); db.commit(); db.refresh(batch)
    else:
        raise HTTPException(status_code=400, detail="Upload mode must be CREATE or UPDATE.")
    try:
        frame = read_upload(file); require_columns(frame, REQUIRED_COLUMNS, "Learners CRM")
        batch.rows_total = len(frame); imported = skipped = 0
        for _, row in frame.iterrows():
            enrolment_id = clean(row.get("enrolmentid")); email = normalize_email(row.get("emailid"))
            if not enrolment_id or not email:
                skipped += 1; continue
            profile = db.scalar(select(LearnersCrmProfile).where(LearnersCrmProfile.normalized_email == email))
            if not profile:
                customer = resolve_customer(db, clean(row.get("learnername")), clean(row.get("emailid")), None)
                profile = LearnersCrmProfile(customer_id=customer.id, learner_name=clean(row.get("learnername")) or "Unknown", email_id=clean(row.get("emailid")), normalized_email=email)
                db.add(profile); db.flush()
            else:
                profile.learner_name = clean(row.get("learnername")) or profile.learner_name
                profile.email_id = clean(row.get("emailid")) or profile.email_id
                customer = resolve_customer(db, profile.learner_name, profile.email_id, None)
                profile.customer_id = customer.id
            mark_customer_converted(db, profile.customer_id)
            enrollment = db.get(LearnersCrmEnrollment, enrolment_id)
            values = {"learner_id": profile.id, "course_name": clean(row.get("coursename")) or "Unknown", "enrolment_date": parse_date(row.get("enrolmentdate")), "start_date": parse_date(row.get("startdate")), "completion_date": parse_date(row.get("completiondate")), "completion_status": clean(row.get("completionstatus")), "upload_batch_id": batch.id}
            if enrollment:
                for key, value in values.items(): setattr(enrollment, key, value)
            else:
                db.add(LearnersCrmEnrollment(enrolment_id=enrolment_id, **values))
            imported += 1
        orphaned = ~select(LearnersCrmEnrollment.enrolment_id).where(LearnersCrmEnrollment.learner_id == LearnersCrmProfile.id).exists()
        db.execute(delete(LearnersCrmProfile).where(orphaned))
        batch.rows_imported = imported; batch.rows_skipped = skipped; batch.status = "COMPLETED"
        db.commit()
        return {"unique_number": batch.unique_number, "rows_total": batch.rows_total, "rows_imported": imported, "rows_skipped": skipped}
    except Exception as exc:
        db.rollback(); failed = db.get(UploadBatch, batch.id)
        if failed:
            failed.status = "FAILED"; failed.error_message = str(exc); db.commit()
        raise HTTPException(status_code=400, detail=str(exc))
