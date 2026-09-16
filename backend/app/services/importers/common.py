import hashlib
import json
import re
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Learner, LearnerCourseRecord


def clean(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    value = str(value).strip()
    return value or None


def normalize_header(value):
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def clean_learner_number(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_date(value):
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    return None if pd.isna(parsed) else parsed.date()


def date_to_iso(value):
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else None


def normalize_result(value):
    value = clean(value)
    if not value:
        return None
    value = value.upper()
    if value in {"PASS", "PASSED"}:
        return "PASS"
    if value in {"FAIL", "FAILED"}:
        return "FAIL"
    if value in {"TBA", "PENDING", "AWAITING"}:
        return "PENDING"
    return value


def normalize_status(value):
    value = clean(value)
    if not value:
        return None
    text = value.upper()
    if "ENROL" in text:
        return "ENROLLED"
    if "PROGRESS" in text:
        return "IN_PROGRESS"
    if "COMPLETE" in text:
        return "COMPLETED"
    if "WITHDRAW" in text:
        return "WITHDRAWN"
    return text


def first_non_empty(row, keys):
    for key in keys:
        value = clean(row.get(key))
        if value is not None:
            return value
    return None


def read_upload(upload_file):
    filename = (upload_file.filename or "").lower()
    upload_file.file.seek(0)
    if filename.endswith(".xlsx"):
        df = pd.read_excel(upload_file.file)
    elif filename.endswith(".csv"):
        df = pd.read_csv(upload_file.file)
    else:
        raise ValueError("Only .xlsx and .csv files are supported.")
    df.columns = [normalize_header(column) for column in df.columns]
    return df


def require_columns(df, required_columns, importer_name):
    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValueError(
            f"{importer_name} file is missing required columns: {', '.join(sorted(missing))}"
        )


def dataframe_row_to_dict(row):
    return {str(key): clean(value) for key, value in row.items()}


def get_profile(row):
    return {
        "learner_number": clean_learner_number(row.get("learnernumber")),
        "name": clean(row.get("name")),
        "nationality": clean(row.get("nationality")),
        "contact_number": clean(row.get("contactnumber")),
        "email_id": clean(row.get("emailid")),
    }


def get_course(db: Session, course_code: str):
    return db.scalar(select(Course).where(Course.code == course_code))


def upsert_learner(
    db: Session,
    learner_number: str,
    name: str | None,
    nationality: str | None,
    contact_number: str | None,
    email_id: str | None,
    event_date: date,
):
    from app.services.customer_identity import mark_customer_converted, resolve_customer

    customer = resolve_customer(db, name, email_id, contact_number)
    learner = db.get(Learner, learner_number)
    if not learner:
        learner = Learner(
            learner_number=learner_number,
            customer_id=customer.id,
            name=name or "Unknown",
            nationality=nationality,
            contact_number=contact_number,
            email_id=email_id,
            last_activity_date=event_date,
        )
        db.add(learner)
        db.flush()
    else:
        learner.customer_id = customer.id
    if learner.last_activity_date is None or event_date >= learner.last_activity_date:
        if name:
            learner.name = name
        if nationality:
            learner.nationality = nationality
        if contact_number:
            learner.contact_number = contact_number
        if email_id:
            learner.email_id = email_id
        learner.last_activity_date = event_date
    db.flush()
    mark_customer_converted(db, customer.id, learner.learner_number)
    return learner


def create_row_hash(learner_number, course_code, event_date, result, enrollment_status, event_type, details):
    payload = {
        "learner_number": learner_number,
        "course_code": course_code,
        "event_date": event_date.isoformat(),
        "event_type": event_type,
        "result": result,
        "enrollment_status": enrollment_status,
        "details": details,
    }
    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_record(db: Session, normalized, raw_data, upload_batch_id):
    course_code = normalized["course_code"]
    course = get_course(db, course_code)
    if not course:
        raise ValueError(
            f"Course '{course_code}' does not exist in the courses table. Add/seed the course first."
        )

    upsert_learner(
        db=db,
        learner_number=normalized["learner_number"],
        name=normalized.get("name"),
        nationality=normalized.get("nationality"),
        contact_number=normalized.get("contact_number"),
        email_id=normalized.get("email_id"),
        event_date=normalized["event_date"],
    )

    row_hash = create_row_hash(
        learner_number=normalized["learner_number"],
        course_code=course_code,
        event_date=normalized["event_date"],
        result=normalized.get("result"),
        enrollment_status=normalized.get("enrollment_status"),
        event_type=normalized["event_type"],
        details=normalized.get("details", {}),
    )

    existing = db.scalar(select(LearnerCourseRecord).where(LearnerCourseRecord.row_hash == row_hash))
    if existing:
        return False

    db.add(LearnerCourseRecord(
        learner_number=normalized["learner_number"],
        course_id=course.id,
        upload_batch_id=upload_batch_id,
        event_date=normalized["event_date"],
        event_type=normalized["event_type"],
        enrollment_status=normalized.get("enrollment_status"),
        result=normalized.get("result"),
        details=normalized.get("details", {}),
        raw_data=raw_data,
        row_hash=row_hash,
    ))
    return True
