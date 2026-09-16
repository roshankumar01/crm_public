from sqlalchemy import delete

from app.database import SessionLocal
from app.models import (
    AuthSession,
    Course,
    Lead,
    LeadActivity,
    Learner,
    LearnerCourseRecord,
    MarketingCampaign,
    UploadBatch,
    User,
)


def reset_everything():
    db = SessionLocal()
    try:
        db.execute(delete(AuthSession))
        db.execute(delete(LeadActivity))
        db.execute(delete(MarketingCampaign))
        db.execute(delete(Lead))
        db.execute(delete(LearnerCourseRecord))
        db.execute(delete(UploadBatch))
        db.execute(delete(Learner))
        db.execute(delete(Course))
        db.execute(delete(User))
        db.commit()
        print("All application data cleared.")
        print(r"Run next: python .\seed_courses.py")
        print(r"Then run: python .\seed_users.py")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    confirmation = input(
        "WARNING: This deletes learners, history, leads, campaigns, uploads, courses AND CRM users.\n"
        "Type DELETE EVERYTHING to continue: "
    )
    if confirmation == "DELETE EVERYTHING":
        reset_everything()
    else:
        print("Reset cancelled.")
