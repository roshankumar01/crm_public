from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect, text
from app.database import Base, SessionLocal, engine
from app.routers import analytics, auth, campaigns, dashboard, learners, learners_crm, leads, main_crm, opportunities, uploads

Base.metadata.create_all(bind=engine)
if "marketing_type" not in {column["name"] for column in inspect(engine).get_columns("marketing_campaigns")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE marketing_campaigns ADD COLUMN marketing_type VARCHAR(100) NOT NULL DEFAULT 'Other'"))
if "email" not in {column["name"] for column in inspect(engine).get_columns("users")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(320)"))
if "region" not in {column["name"] for column in inspect(engine).get_columns("users")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN region VARCHAR(255)"))
if "country" not in {column["name"] for column in inspect(engine).get_columns("users")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN country VARCHAR(100)"))
if "customer_id" not in {column["name"] for column in inspect(engine).get_columns("main_crm_leads")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE main_crm_leads ADD COLUMN customer_id INTEGER"))
        connection.execute(text("CREATE INDEX ix_main_crm_leads_customer_id ON main_crm_leads (customer_id)"))
if "country" not in {column["name"] for column in inspect(engine).get_columns("main_crm_leads")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE main_crm_leads ADD COLUMN country VARCHAR(100)"))
        connection.execute(text("CREATE INDEX ix_main_crm_leads_country ON main_crm_leads (country)"))
if "customer_id" not in {column["name"] for column in inspect(engine).get_columns("learners_crm_profiles")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE learners_crm_profiles ADD COLUMN customer_id INTEGER"))
        connection.execute(text("CREATE INDEX ix_learners_crm_profiles_customer_id ON learners_crm_profiles (customer_id)"))
if "customer_id" not in {column["name"] for column in inspect(engine).get_columns("learners")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE learners ADD COLUMN customer_id INTEGER"))
        connection.execute(text("CREATE INDEX ix_learners_customer_id ON learners (customer_id)"))
if "unique_number" not in {column["name"] for column in inspect(engine).get_columns("upload_batches")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE upload_batches ADD COLUMN unique_number VARCHAR(50)"))
        connection.execute(text("CREATE UNIQUE INDEX ix_upload_batches_unique_number ON upload_batches (unique_number)"))
with engine.begin() as connection:
    connection.execute(text("UPDATE users SET email = 'person_a@gmail.com' WHERE username = 'person_a' AND email IS NULL"))
    connection.execute(text("UPDATE users SET email = 'person_b@gmail.com' WHERE username = 'person_b' AND email IS NULL"))

from app.services.customer_identity import backfill_customer_links
with SessionLocal() as session:
    backfill_customer_links(session)

app = FastAPI(title="Learning CRM API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(learners.router)
app.include_router(opportunities.router)
app.include_router(leads.router)
app.include_router(analytics.router)
app.include_router(campaigns.router)
app.include_router(uploads.router)
app.include_router(main_crm.router)
app.include_router(learners_crm.router)


@app.get("/health")
def health():
    return {"status": "ok"}
