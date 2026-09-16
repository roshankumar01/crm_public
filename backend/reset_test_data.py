from sqlalchemy import delete

from app.database import SessionLocal
from app.models import Lead, LeadActivity, Learner, LearnerCourseRecord, MarketingCampaign, UploadBatch


def reset_test_data():
    db = SessionLocal()
    try:
        db.execute(delete(LeadActivity))
        db.execute(delete(MarketingCampaign))
        db.execute(delete(Lead))
        db.execute(delete(LearnerCourseRecord))
        db.execute(delete(UploadBatch))
        db.execute(delete(Learner))
        db.commit()
        print("Test data reset successfully. Courses and CRM users were preserved.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    confirmation = input(
        "This will DELETE all learners, course history, leads, campaign history and upload history.\n"
        "CRM users and courses will be preserved.\n"
        "Type RESET to continue: "
    )
    if confirmation == "RESET":
        reset_test_data()
    else:
        print("Reset cancelled.")
