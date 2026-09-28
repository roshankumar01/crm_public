from datetime import datetime, timezone
import secrets
from io import BytesIO
import pandas as pd
from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LearnersCrmEnrollment, LearnersCrmProfile, MainCrmLead, UploadBatch, User
from app.services.auth import get_current_user, require_admin
from app.services.customer_identity import mark_customer_converted, normalize_phone, resolve_customer
from app.services.customer_lifecycle import customer_lifecycle
from app.services.counselor_sync import main_counselors, counselor_fields
from app.services.importers.common import clean, clean_learner_number, dataframe_row_to_dict, parse_date, read_upload, require_columns, upload_chunks
from app.services.learner_course_mapping import categories_for_course_names, mapping_for_course_names, normalize_course_name
from app.services.lead_workflow import mark_opportunities_dirty
from app.services.date_filters import period_condition

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
def overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db), period: str = "all"):
    enrolment_filters = period_condition(LearnersCrmEnrollment.created_at, period)
    filtered_profile_ids = select(LearnersCrmEnrollment.learner_id).where(*enrolment_filters).distinct().subquery()
    total_learners = db.scalar(select(func.count()).select_from(filtered_profile_ids)) or 0
    total_enrolments = db.scalar(select(func.count()).select_from(LearnersCrmEnrollment).where(*enrolment_filters)) or 0
    normalized_status = func.upper(func.trim(LearnersCrmEnrollment.completion_status))
    status_counts = dict(db.execute(select(normalized_status, func.count()).select_from(
        LearnersCrmEnrollment).where(*enrolment_filters).group_by(normalized_status)).all())
    active = status_counts.get("NOT COMPLETED", 0)
    completed = status_counts.get("COMPLETED", 0)
    matched_enquiries = db.scalar(select(func.count()).select_from(LearnersCrmProfile).where(LearnersCrmProfile.id.in_(select(filtered_profile_ids.c.learner_id)),
        select(MainCrmLead.id).where(MainCrmLead.normalized_email == LearnersCrmProfile.normalized_email).exists()
    )) or 0
    course_rows = db.execute(select(LearnersCrmEnrollment.course_name, func.count()).where(*enrolment_filters).group_by(
        LearnersCrmEnrollment.course_name
    )).all()
    mapped_categories = categories_for_course_names(db, [name for name, _ in course_rows])
    category_counts = Counter()
    for name, count in course_rows:
        category_counts[mapped_categories.get(normalize_course_name(name), "Unmapped")] += count
    return {"total_learners": total_learners, "total_enrolments": total_enrolments, "completed": completed, "active": active, "matched_enquiries": matched_enquiries, "course_categories": [{"name": name, "enrolments": count} for name, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))]}


@router.get("/export")
def export_learners(period: str = "all", current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filters = period_condition(LearnersCrmEnrollment.created_at, period)
    rows = db.execute(select(LearnersCrmProfile, LearnersCrmEnrollment).join(LearnersCrmEnrollment, LearnersCrmEnrollment.learner_id == LearnersCrmProfile.id).where(*filters).order_by(LearnersCrmEnrollment.created_at.desc())).all()
    owners = main_counselors(db, [profile.customer_id for profile, _ in rows])
    values = [{"Counselor": counselor_fields(owners, profile.customer_id)["assigned_to_name"] or "Unassigned",
               "Counselor Email": counselor_fields(owners, profile.customer_id)["assigned_to_email"], "Learner": profile.learner_name, "Email": profile.email_id, "Phone": profile.phone_number,
               "Enrolment ID": enrollment.enrolment_id, "Course": enrollment.course_name,
               "Enrolment Date": enrollment.enrolment_date, "Completion Date": enrollment.completion_date,
               "Completion Status": enrollment.completion_status, "Created At": enrollment.created_at,
               "Updated At": enrollment.updated_at} for profile, enrollment in rows]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer: pd.DataFrame(values).to_excel(writer, sheet_name="Learners CRM", index=False)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="learners-crm-export.xlsx"'})


@router.get("/learners")
def search_learners(
    search: str = Query("", max_length=320),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
    page: int = 1,
):
    page = max(1, page)
    query = search.strip()
    if query:
        enrolment_match = select(LearnersCrmEnrollment.enrolment_id).where(
            LearnersCrmEnrollment.learner_id == LearnersCrmProfile.id,
            func.lower(LearnersCrmEnrollment.enrolment_id).contains(query.lower()),
        ).exists()
        conditions = [LearnersCrmProfile.normalized_email.contains(query.lower()), enrolment_match]
        phone_query = normalize_phone(query)
        if phone_query and len(phone_query) >= 3 and not any(character.isalpha() for character in query):
            conditions.append(LearnersCrmProfile.normalized_phone.contains(phone_query))
        statement = select(LearnersCrmProfile).where(or_(*conditions)).order_by(LearnersCrmProfile.learner_name, LearnersCrmProfile.id).offset((page - 1) * 25).limit(25)
    else:
        latest_enrolment = select(
            LearnersCrmEnrollment.learner_id,
            func.max(LearnersCrmEnrollment.updated_at).label("last_updated"),
        ).group_by(LearnersCrmEnrollment.learner_id).subquery()
        statement = select(LearnersCrmProfile).outerjoin(
            latest_enrolment, latest_enrolment.c.learner_id == LearnersCrmProfile.id
        ).order_by(latest_enrolment.c.last_updated.desc(), LearnersCrmProfile.id.desc()).offset((page - 1) * 25).limit(25)
    profiles = db.execute(statement).scalars().all()
    return learner_profiles_payload(db, profiles, preview_limit=5)


def learner_profiles_payload(db, profiles, preview_limit=None):
    if not profiles:
        return []
    owners = main_counselors(db, [profile.customer_id for profile in profiles])
    profile_ids = [profile.id for profile in profiles]
    statement = select(LearnersCrmEnrollment).where(LearnersCrmEnrollment.learner_id.in_(profile_ids))
    if preview_limit is not None:
        ranked = select(
            LearnersCrmEnrollment.enrolment_id.label("id"),
            func.row_number().over(partition_by=LearnersCrmEnrollment.learner_id,
                order_by=(LearnersCrmEnrollment.enrolment_date.desc(), LearnersCrmEnrollment.enrolment_id)).label("rank"),
        ).where(LearnersCrmEnrollment.learner_id.in_(profile_ids)).subquery()
        statement = statement.join(ranked, LearnersCrmEnrollment.enrolment_id == ranked.c.id).where(ranked.c.rank <= preview_limit)
    enrolments = db.scalars(statement.order_by(LearnersCrmEnrollment.enrolment_date.desc(), LearnersCrmEnrollment.enrolment_id)).all()
    mapped_categories = mapping_for_course_names(db, [enrolment.course_name for enrolment in enrolments])
    by_learner = {profile.id: [] for profile in profiles}
    for enrolment in enrolments:
        by_learner[enrolment.learner_id].append({
            "enrolment_id": enrolment.enrolment_id,
            "course_name": enrolment.course_name,
            "course_category": (mapped_categories.get(normalize_course_name(enrolment.course_name)) or {}).get("main_category"),
            "course_sub_category": (mapped_categories.get(normalize_course_name(enrolment.course_name)) or {}).get("sub_category"),
            "enrolment_date": enrolment.enrolment_date,
            "start_date": enrolment.start_date,
            "completion_date": enrolment.completion_date,
            "completion_status": enrolment.completion_status,
            "created_at": enrolment.created_at,
            "updated_at": enrolment.updated_at,
        })
    return [{
        **counselor_fields(owners, profile.customer_id),
        "id": profile.id, "learner_name": profile.learner_name,
        "email_id": profile.email_id, "phone_number": profile.phone_number,
        "created_at": profile.created_at, "updated_at": profile.updated_at,
        "enrolments": by_learner[profile.id],
    } for profile in profiles]


@router.get("/learners/{learner_id}")
def get_learner_profile(learner_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(LearnersCrmProfile, learner_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Learner not found.")
    return {**learner_profiles_payload(db, [profile])[0],
            "lifecycle": customer_lifecycle(db, profile.customer_id, current_user)}


@router.get("/uploads")
def uploads(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(UploadBatch).where(UploadBatch.import_type == "LEARNERS_CRM").order_by(UploadBatch.uploaded_at.desc(), UploadBatch.id.desc())).scalars().all()
    return [{"id": row.id, "unique_number": row.unique_number, "filename": row.filename, "status": row.status, "rows_total": row.rows_total, "rows_imported": row.rows_imported, "rows_skipped": row.rows_skipped, "uploaded_at": row.uploaded_at} for row in rows]


@router.post("/upload")
def upload(
    file: Annotated[UploadFile, File()], upload_mode: Annotated[str, Form()] = "CREATE",
    unique_number: Annotated[str | None, Form()] = None,
    admin: User = Depends(require_admin), db: Session = Depends(get_db),
    progress=None,
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
        batch.rows_total = len(frame); imported = skipped = mapped = 0; skipped_rows = []
        if progress:
            progress(rows_total=len(frame))
        mapped_categories = categories_for_course_names(db, [clean(value) for value in frame["coursename"]])
        unmapped_courses = set()
        converted_ids = set()
        for processed, rows in upload_chunks(frame):
            emails = {normalize_email(row.get("emailid")) for row in rows}
            enrolment_ids = {clean(row.get("enrolmentid")) for row in rows}
            profiles = {item.normalized_email: item for item in db.scalars(select(LearnersCrmProfile).where(
                LearnersCrmProfile.normalized_email.in_(emails - {None})
            ))}
            enrolments = {item.enrolment_id: item for item in db.scalars(select(LearnersCrmEnrollment).where(
                LearnersCrmEnrollment.enrolment_id.in_(enrolment_ids - {None})
            ))}
            resolved_emails = set()
            for row in rows:
                enrolment_id = clean(row.get("enrolmentid")); email = normalize_email(row.get("emailid"))
                if not enrolment_id or not email:
                    skipped += 1; skipped_rows.append({"row_number": processed - len(rows) + rows.index(row) + 2, "reason": "Missing enrolment ID or email", **dataframe_row_to_dict(row)}); continue
                phone = clean_learner_number(row.get("phonenumber")) if "phonenumber" in frame.columns else None
                profile = profiles.get(email)
                if not profile:
                    customer = resolve_customer(db, clean(row.get("learnername")), clean(row.get("emailid")), phone)
                    profile = LearnersCrmProfile(customer_id=customer.id, learner_name=clean(row.get("learnername")) or "Unknown", email_id=clean(row.get("emailid")), normalized_email=email, phone_number=phone, normalized_phone=normalize_phone(phone))
                    db.add(profile); db.flush()
                    profiles[email] = profile
                    resolved_emails.add(email)
                else:
                    profile.learner_name = clean(row.get("learnername")) or profile.learner_name
                    profile.email_id = clean(row.get("emailid")) or profile.email_id
                    phone_changed = bool(phone and phone != profile.phone_number)
                    if phone:
                        profile.phone_number = phone
                        profile.normalized_phone = normalize_phone(phone)
                    if email not in resolved_emails or phone_changed or not profile.customer_id:
                        customer = resolve_customer(db, profile.learner_name, profile.email_id, profile.phone_number)
                        profile.customer_id = customer.id
                        resolved_emails.add(email)
                if profile.customer_id not in converted_ids:
                    mark_customer_converted(db, profile.customer_id)
                    converted_ids.add(profile.customer_id)
                course_name = clean(row.get("coursename")) or "Unknown"
                if normalize_course_name(course_name) in mapped_categories:
                    mapped += 1
                else:
                    unmapped_courses.add(course_name)
                enrollment = enrolments.get(enrolment_id)
                values = {"learner_id": profile.id, "course_name": course_name, "enrolment_date": parse_date(row.get("enrolmentdate")), "start_date": parse_date(row.get("startdate")), "completion_date": parse_date(row.get("completiondate")), "completion_status": clean(row.get("completionstatus")), "upload_batch_id": batch.id}
                if enrollment:
                    for key, value in values.items(): setattr(enrollment, key, value)
                else:
                    enrollment = LearnersCrmEnrollment(enrolment_id=enrolment_id, **values)
                    db.add(enrollment)
                    enrolments[enrolment_id] = enrollment
                imported += 1
            db.flush()
            if progress:
                progress(processed=processed, rows_imported=imported, rows_skipped=skipped,
                         rows_mapped=mapped)
        orphaned = ~select(LearnersCrmEnrollment.enrolment_id).where(LearnersCrmEnrollment.learner_id == LearnersCrmProfile.id).exists()
        db.execute(delete(LearnersCrmProfile).where(orphaned))
        batch.rows_imported = imported; batch.rows_skipped = skipped; batch.status = "COMPLETED"
        if imported or mode == "UPDATE":
            mark_opportunities_dirty(db)
        db.commit()
        return {"unique_number": batch.unique_number, "rows_total": batch.rows_total, "rows_imported": imported, "rows_skipped": skipped, "rows_mapped": mapped, "unmapped_courses": sorted(unmapped_courses), "skipped_rows": skipped_rows}
    except Exception as exc:
        db.rollback(); failed = db.get(UploadBatch, batch.id)
        if failed:
            failed.status = "FAILED"; failed.error_message = str(exc); db.commit()
        raise HTTPException(status_code=400, detail=str(exc))
