from sqlalchemy.orm import Session

from app.models import UploadBatch
from app.services.importers.common import dataframe_row_to_dict, read_upload, save_record
from app.services.importers.registry import get_importer


def import_course_file(db: Session, import_type: str, upload_file):
    importer = get_importer(import_type)

    batch = UploadBatch(
        import_type=importer.import_type,
        filename=upload_file.filename or "unknown",
        status="PROCESSING",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    try:
        df = read_upload(upload_file)
        batch.rows_total = len(df)
        importer.validate_columns(df)

        imported = 0
        skipped = 0

        for _, row in df.iterrows():
            raw_data = dataframe_row_to_dict(row)
            normalized_records = importer.parse_row(row)
            if not normalized_records:
                skipped += 1
                continue

            for normalized in normalized_records:
                if save_record(db, normalized, raw_data, batch.id):
                    imported += 1
                else:
                    skipped += 1

        batch.rows_imported = imported
        batch.rows_skipped = skipped
        batch.status = "COMPLETED"
        db.commit()
        db.refresh(batch)
        return batch

    except Exception as exc:
        db.rollback()
        failed_batch = db.get(UploadBatch, batch.id)
        if failed_batch:
            failed_batch.status = "FAILED"
            failed_batch.error_message = str(exc)
            db.commit()
        raise
