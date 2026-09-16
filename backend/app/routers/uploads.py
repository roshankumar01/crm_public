from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Lead, LeadActivity, Learner, LearnerCourseRecord, LearnersCrmEnrollment,
    LearnersCrmProfile, MainCrmActivity, MainCrmLead, MarketingCampaign, UploadBatch, User,
)
from app.services.auth import require_admin
from app.services.importers import import_course_file, list_importers

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class ResetUploadsRequest(BaseModel):
    upload_ids: list[int]
    confirmation: str


@router.get("/reset-options")
def reset_options(admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    batches = db.execute(select(UploadBatch).order_by(UploadBatch.uploaded_at.desc(), UploadBatch.id.desc())).scalars().all()
    return [{
        "id": batch.id, "filename": batch.filename, "import_type": batch.import_type,
        "unique_number": batch.unique_number, "rows_imported": batch.rows_imported,
        "uploaded_at": batch.uploaded_at,
    } for batch in batches]


@router.post("/reset")
def reset_selected_uploads(
    payload: ResetUploadsRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ids = set(payload.upload_ids)
    if not ids or len(ids) != len(payload.upload_ids) or any(item <= 0 for item in ids):
        raise HTTPException(status_code=400, detail="Select one or more valid upload files.")
    if payload.confirmation != "DELETE SELECTED UPLOADS":
        raise HTTPException(status_code=400, detail="Type DELETE SELECTED UPLOADS to confirm.")
    batches = db.execute(select(UploadBatch).where(UploadBatch.id.in_(ids))).scalars().all()
    if len(batches) != len(ids):
        raise HTTPException(status_code=404, detail="One or more selected uploads no longer exist. Refresh and try again.")

    try:
        # Remove only records with explicit provenance to a selected upload.
        affected_learner_numbers = set(db.execute(select(LearnerCourseRecord.learner_number).where(
            LearnerCourseRecord.upload_batch_id.in_(ids)
        )).scalars().all())
        affected_learner_numbers.update(db.execute(select(MarketingCampaign.learner_number).where(
            MarketingCampaign.upload_batch_id.in_(ids)
        )).scalars().all())
        affected_profile_ids = set(db.execute(select(LearnersCrmEnrollment.learner_id).where(
            LearnersCrmEnrollment.upload_batch_id.in_(ids)
        )).scalars().all())
        db.execute(delete(MainCrmActivity).where(MainCrmActivity.upload_batch_id.in_(ids)))
        db.execute(delete(LearnerCourseRecord).where(LearnerCourseRecord.upload_batch_id.in_(ids)))
        db.execute(delete(MarketingCampaign).where(MarketingCampaign.upload_batch_id.in_(ids)))
        db.execute(delete(LearnersCrmEnrollment).where(LearnersCrmEnrollment.upload_batch_id.in_(ids)))

        # A shared lead may still have activity from another upload. Preserve it.
        has_activity = select(MainCrmActivity.id).where(MainCrmActivity.lead_id == MainCrmLead.id).exists()
        db.execute(delete(MainCrmLead).where(MainCrmLead.upload_batch_id.in_(ids), ~has_activity))
        db.execute(update(MainCrmLead).where(MainCrmLead.upload_batch_id.in_(ids)).values(upload_batch_id=None))

        # Only profiles touched by selected files are eligible for orphan cleanup.
        has_enrolment = select(LearnersCrmEnrollment.enrolment_id).where(
            LearnersCrmEnrollment.learner_id == LearnersCrmProfile.id
        ).exists()
        if affected_profile_ids:
            db.execute(delete(LearnersCrmProfile).where(LearnersCrmProfile.id.in_(affected_profile_ids), ~has_enrolment))

        # An Upsell learner is removed only when no other import or manually
        # maintained lead history still refers to that learner.
        for learner_number in affected_learner_numbers:
            has_course = db.scalar(select(LearnerCourseRecord.id).where(LearnerCourseRecord.learner_number == learner_number).limit(1))
            has_campaign = db.scalar(select(MarketingCampaign.id).where(MarketingCampaign.learner_number == learner_number).limit(1))
            has_main_crm_link = db.scalar(select(MainCrmLead.id).where(MainCrmLead.matched_learner_number == learner_number).limit(1))
            lead_ids = select(Lead.id).where(Lead.learner_number == learner_number)
            has_manual_history = db.scalar(select(LeadActivity.id).where(LeadActivity.lead_id.in_(lead_ids)).limit(1))
            if not (has_course or has_campaign or has_main_crm_link or has_manual_history):
                db.execute(delete(Lead).where(Lead.learner_number == learner_number))
                db.execute(delete(Learner).where(Learner.learner_number == learner_number))

        db.execute(delete(UploadBatch).where(UploadBatch.id.in_(ids)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"uploads_deleted": len(ids)}


@router.get("/import-types")
def get_import_types(admin_user: User = Depends(require_admin)):
    return [
        {
            "import_type": item.import_type,
            "display_name": item.display_name,
            "description": item.description,
            "columns": item.columns,
        }
        for item in list_importers()
    ]


@router.get("")
def get_uploads(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(UploadBatch).order_by(UploadBatch.uploaded_at.desc()).limit(50)
    ).scalars().all()


@router.post("")
def upload_excel(
    import_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        batch = import_course_file(db, import_type, file)
        return {
            "id": batch.id,
            "filename": batch.filename,
            "import_type": batch.import_type,
            "status": batch.status,
            "rows_total": batch.rows_total,
            "rows_imported": batch.rows_imported,
            "rows_skipped": batch.rows_skipped,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
