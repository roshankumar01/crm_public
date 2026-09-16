import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    Learner, LearnerCourseRecord, LearnersCrmEnrollment, LearnersCrmProfile,
    MainCrmActivity, MainCrmLead, MarketingCampaign, UploadBatch, User, Course,
)
from app.routers.uploads import ResetUploadsRequest, reset_selected_uploads


class UploadResetTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username="admin", display_name="Admin", password_hash="x", role="ADMIN", active=True)
        self.db.add(self.admin)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_selected_main_crm_upload_preserves_shared_lead(self):
        first = UploadBatch(import_type="MAIN_CRM_INFO_EMAIL_LEADS", filename="first.csv")
        second = UploadBatch(import_type="MAIN_CRM_LIVE_ONLINE_LEADS", filename="second.csv")
        self.db.add_all([first, second])
        self.db.flush()
        lead = MainCrmLead(full_name="Shared", source_category="LIVE_ONLINE_LEADS", upload_batch_id=first.id)
        self.db.add(lead)
        self.db.flush()
        self.db.add_all([
            MainCrmActivity(lead_id=lead.id, upload_batch_id=first.id, activity_type="ENQUIRY"),
            MainCrmActivity(lead_id=lead.id, upload_batch_id=second.id, activity_type="ENQUIRY"),
        ])
        self.db.commit()

        result = reset_selected_uploads(ResetUploadsRequest(upload_ids=[first.id], confirmation="DELETE SELECTED UPLOADS"), self.admin, self.db)
        self.assertEqual(result["uploads_deleted"], 1)
        self.assertIsNone(self.db.get(UploadBatch, first.id))
        self.assertIsNotNone(self.db.get(UploadBatch, second.id))
        self.assertIsNone(self.db.get(MainCrmLead, lead.id).upload_batch_id)
        self.assertEqual([item.upload_batch_id for item in self.db.scalars(select(MainCrmActivity)).all()], [second.id])

    def test_selected_learner_upload_only_removes_its_enrolments(self):
        first = UploadBatch(import_type="LEARNERS_CRM", filename="first.csv")
        second = UploadBatch(import_type="LEARNERS_CRM", filename="second.csv")
        self.db.add_all([first, second])
        self.db.flush()
        profile = LearnersCrmProfile(learner_name="Shared", email_id="s@example.com", normalized_email="s@example.com")
        self.db.add(profile)
        self.db.flush()
        self.db.add_all([
            LearnersCrmEnrollment(enrolment_id="a", learner_id=profile.id, course_name="A", upload_batch_id=first.id),
            LearnersCrmEnrollment(enrolment_id="b", learner_id=profile.id, course_name="B", upload_batch_id=second.id),
        ])
        self.db.commit()
        reset_selected_uploads(ResetUploadsRequest(upload_ids=[first.id], confirmation="DELETE SELECTED UPLOADS"), self.admin, self.db)
        self.assertIsNone(self.db.get(LearnersCrmEnrollment, "a"))
        self.assertIsNotNone(self.db.get(LearnersCrmEnrollment, "b"))
        self.assertIsNotNone(self.db.get(LearnersCrmProfile, profile.id))

    def test_selected_upsell_upload_removes_orphan_learner(self):
        batch = UploadBatch(import_type="IGC", filename="igc.csv")
        course = Course(code="IGC", name="IGC", program_code="IGC")
        learner = Learner(learner_number="L1", name="Learner")
        self.db.add_all([batch, course, learner])
        self.db.flush()
        self.db.add(LearnerCourseRecord(learner_number="L1", course_id=course.id, upload_batch_id=batch.id,
            event_date=__import__("datetime").date(2026, 1, 1), row_hash="unique"))
        self.db.commit()
        reset_selected_uploads(ResetUploadsRequest(upload_ids=[batch.id], confirmation="DELETE SELECTED UPLOADS"), self.admin, self.db)
        self.assertIsNone(self.db.get(Learner, "L1"))
        self.assertIsNotNone(self.db.get(Course, course.id))

    def test_confirmation_and_missing_ids_do_not_delete(self):
        batch = UploadBatch(import_type="MARKETING_CAMPAIGN", filename="campaign.csv")
        self.db.add(batch)
        self.db.commit()
        for payload in (
            ResetUploadsRequest(upload_ids=[batch.id], confirmation="wrong"),
            ResetUploadsRequest(upload_ids=[batch.id, 9999], confirmation="DELETE SELECTED UPLOADS"),
        ):
            with self.assertRaises(HTTPException):
                reset_selected_uploads(payload, self.admin, self.db)
            self.assertIsNotNone(self.db.get(UploadBatch, batch.id))


if __name__ == "__main__":
    unittest.main()
