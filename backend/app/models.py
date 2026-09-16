from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    primary_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    primary_phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CustomerIdentity(Base):
    __tablename__ = "customer_identities"
    __table_args__ = (UniqueConstraint("identity_type", "normalized_value", name="uq_customer_identity_value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    identity_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    normalized_value: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    raw_value: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Learner(Base):
    __tablename__ = "learners"

    learner_number: Mapped[str] = mapped_column(String(50), primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nationality: Mapped[str | None] = mapped_column(String(100))
    contact_number: Mapped[str | None] = mapped_column(String(100))
    email_id: Mapped[str | None] = mapped_column(String(320))
    last_activity_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    course_records: Mapped[list["LearnerCourseRecord"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    program_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    records: Mapped[list["LearnerCourseRecord"]] = relationship(back_populates="course")


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_type: Mapped[str] = mapped_column(String(50), nullable=False)
    unique_number: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PROCESSING", nullable=False)
    rows_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LearnerCourseRecord(Base):
    __tablename__ = "learner_course_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_number: Mapped[str] = mapped_column(
        ForeignKey("learners.learner_number", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), default="COURSE_RESULT", nullable=False)
    enrollment_status: Mapped[str | None] = mapped_column(String(50))
    result: Mapped[str | None] = mapped_column(String(50))
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    learner: Mapped["Learner"] = relationship(back_populates="course_records")
    course: Mapped["Course"] = relationship(back_populates="records")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("learner_number", "opportunity_key", name="uq_lead_learner_opportunity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_number: Mapped[str] = mapped_column(
        ForeignKey("learners.learner_number", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    trigger_date: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False, index=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    channel: Mapped[str | None] = mapped_column(String(30), index=True)
    campaign_name: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_number: Mapped[str] = mapped_column(
        ForeignKey("learners.learner_number", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    marketing_type: Mapped[str] = mapped_column(String(100), nullable=False, default="Other", index=True)
    upload_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MainCrmLead(Base):
    __tablename__ = "main_crm_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    normalized_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    normalized_phone: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    whatsapp_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    course: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_of_lead: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False, index=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sales_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_learner_number: Mapped[str | None] = mapped_column(
        ForeignKey("learners.learner_number", ondelete="SET NULL"), nullable=True, index=True
    )
    upload_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MainCrmActivity(Base):
    __tablename__ = "main_crm_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("main_crm_leads.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=True, index=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    activity_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    campaign_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    campaign_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    course: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_user_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LearnersCrmProfile(Base):
    __tablename__ = "learners_crm_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    learner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email_id: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LearnersCrmEnrollment(Base):
    __tablename__ = "learners_crm_enrollments"

    enrolment_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners_crm_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    enrolment_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_status: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    upload_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
