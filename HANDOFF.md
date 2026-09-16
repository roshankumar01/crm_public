# Learning CRM — New Chat Handoff

## Read this first

> **Current-state note (September 2026):** The original Stage 1 sections below remain useful for the Upsell CRM, but the application has since expanded into two connected workspaces. The "Full CRM expansion" section near the end of this file supersedes older route and limitation notes.

This repository is the latest agreed snapshot of a teaching-company CRM project. Inspect this file and the repository before changing code.

When changing code for the user:

1. explain what changed
2. explain why
3. give the **full replacement content** of each changed file, not only a diff
4. mention any DB/setup/migration step
5. keep explanations beginner-friendly
6. preserve working architecture unless there is a real reason to change it

---

## Business model

Current courses:

- IGC
- ID1
- ID2
- ID3

Important:

- `IDP` is **not a course**.
- IDP is a program/family containing `ID1`, `ID2`, `ID3`.
- ID1/ID2/ID3 are independent courses and have no fixed order.
- Stage 1 trusts `learner_number` as the unique learner key.
- No ML/DL yet. Everything is rule-based Python.

---

## Current opportunity/recommendation rules

Single source of truth:

```text
backend/app/services/course_rules.py
```

Do not duplicate these rules in React or importer files.

### IGC → IDP Entry

If learner completed/passed IGC and has **no activity** in ID1, ID2 or ID3:

```text
IDP Entry lead
```

### Cross-sell within IDP

Once a learner completes any ID course, every other ID course they have **never entered** becomes an opportunity.

Examples:

```text
ID1 PASS -> ID2 + ID3
ID2 PASS -> ID1 + ID3
ID3 PASS -> ID1 + ID2
ID1 PASS + ID3 PASS -> ID2
ID1 PASS + ID2 PASS -> ID3
ID2 PASS + ID3 PASS -> ID1
ID1 + ID2 + ID3 complete -> no current ID opportunity
```

Existing activity prevents recommending the same target again.

Example:

```text
ID1 PASS
ID2 ENROLLED
```

Expected:

```text
ID3 only
```

---

## Main pages

```text
/                     Dashboard
/learners             Learners/search
/learners/:id         Learner profile + learning journey
/opportunities        Generic Opportunities page
/uploads              Excel/CSV uploads
```

Compatibility route:

```text
/opportunities/idp
```

currently opens the generic Opportunities page.

---

## Opportunities page

Sections:

1. IDP Entry
2. ID1 Opportunities
3. ID2 Opportunities
4. ID3 Opportunities

One learner can produce more than one opportunity.

Example:

```text
ID1 PASS
```

means:

```text
1 opportunity learner
2 opportunities (ID2 and ID3)
```

---

## Database

Main tables:

```text
learners
courses
learner_course_records
upload_batches
```

### learners

Current learner profile. Key:

```text
learner_number
```

### courses

Current seed:

```text
IGC  -> program_code IGC
ID1  -> program_code IDP
ID2  -> program_code IDP
ID3  -> program_code IDP
```

There is no IDP course row.

### learner_course_records

Immutable dated learning history.

Important fields:

```text
learner_number
course_id
event_date
event_type
enrollment_status
result
details JSON
raw_data JSON
row_hash
```

Do not overwrite old history.

### upload_batches

Tracks each uploaded file and its import status/counts.

---

## Learner journey

The learner profile should visually show chronological learning history and recommendations.

Example:

```text
01 May 2026
IGC - FAIL
IG1 48
IG2 60

20 May 2026
IGC - PASS
IG1 75
IG2 100

10 Jun 2026
ID1 - PASS
```

Course-specific `details` JSON is rendered dynamically in the frontend, so many new display-only fields require no frontend change.

---

## Upload architecture

Course-specific importer files live in:

```text
backend/app/services/importers/
```

Current files:

```text
common.py
registry.py
service.py
igc.py
idp.py
```

### common.py

Shared logic:

- value cleaning
- header normalization
- date parsing
- result/status normalization
- learner upsert
- duplicate row hash
- database save

### registry.py

Automatically discovers importer files.

Every course importer must expose:

```python
IMPORT_TYPE
DISPLAY_NAME
DESCRIPTION

def validate_columns(df):
    ...

def parse_row(row):
    ...
```

### service.py

Generic upload coordinator. It must **not** contain course-specific Excel mapping.

### igc.py

Only IGC Excel knowledge.

### idp.py

Only ID1/ID2/ID3 Excel knowledge.

---

## Current IGC Excel expectations

Headers are normalized by removing capitalization, spaces, `_`, `-`, etc.

Examples:

```text
Learner number
Learner_Number
LEARNER-NUMBER
```

all become:

```text
learnernumber
```

Required IGC headers after normalization:

```text
learnernumber
date
overallresult
```

Optional/currently supported:

```text
name
nationality
contactnumber
emailid
ig1result
ig2result
unit
bilingualdictionary
reg
```

IGC currently creates a `COURSE_RESULT` event.

---

## Current IDP Excel expectations

Here `IDP Excel` means one file containing activity/results for the ID course family.

Supported preliminary formats:

### Format A

```text
Learner number | Course | Result | Status | date
```

Course-like header may be:

```text
Course
Course Code
Module
Unit
```

Course values can include ID1, ID2, ID3.

### Format B

```text
Learner number | ID1 Result | ID2 Result | ID3 Result | date
```

One spreadsheet row may create multiple DB records.

When a real IDP spreadsheet is supplied, normally update only:

```text
backend/app/services/importers/idp.py
```

---

## Adding a future course

Example: IELTS.

### 1. Add course catalog entry

Update:

```text
backend/seed_courses.py
```

then run:

```powershell
python .\seed_courses.py
```

### 2. Add importer

Create:

```text
backend/app/services/importers/ielts.py
```

with metadata, `validate_columns()` and `parse_row()`.

The importer registry discovers it automatically, and the frontend upload dropdown reads available importers from:

```text
GET /uploads/import-types
```

Normally you do **not** update registry.py, service.py, uploads.py, api.js or UploadsPage.jsx for each new importer.

---

## Adding a new Excel column

### Display-only/course-specific field

Examples:

```text
Exam Centre
Teacher
Batch
```

Usually change only the relevant importer and add the value to `details`.

### Lifecycle date

Examples:

```text
Registered Date
Exam Date
Completion Date
Withdrawal Date
```

Prefer creating separate lifecycle records when it represents a real event.

The importer `parse_row()` returns a **list** intentionally, so one Excel row can create several timeline events.

Example:

```text
Registered Date = 01-05-2026
Exam Date       = 01-06-2026
PASS
```

could become:

```text
01-05-2026  IGC ENROLMENT / ENROLLED
01-06-2026  IGC COURSE_RESULT / PASS
```

### Important globally queried field

If a field becomes heavily used for filtering/reporting/business logic, consider a real database column. That would require a schema migration plus importer/API/query changes.

---

## Important file map

| Requirement | File |
|---|---|
| Progression rules | `backend/app/services/course_rules.py` |
| Learner recommendation adapter | `backend/app/services/recommendation.py` |
| Opportunity grouping | `backend/app/services/opportunities.py` |
| IGC Excel format | `backend/app/services/importers/igc.py` |
| IDP Excel format | `backend/app/services/importers/idp.py` |
| Common upload helpers | `backend/app/services/importers/common.py` |
| Importer auto-discovery | `backend/app/services/importers/registry.py` |
| Generic upload coordinator | `backend/app/services/importers/service.py` |
| Course catalog | `backend/seed_courses.py` |
| DB models | `backend/app/models.py` |
| Learner API | `backend/app/routers/learners.py` |
| Opportunity API | `backend/app/routers/opportunities.py` |
| Upload API | `backend/app/routers/uploads.py` |
| Dashboard API | `backend/app/routers/dashboard.py` |
| Frontend API client | `frontend/src/api.js` |
| Journey UI | `frontend/src/pages/LearnerDetailPage.jsx` |
| Opportunity UI | `frontend/src/pages/OpportunitiesPage.jsx` |
| Upload UI | `frontend/src/pages/UploadsPage.jsx` |

---

## PowerShell first-time backend setup

Create PostgreSQL database `upsell_db`, then create `backend\.env` from `.env.example`.

```powershell
cd .\backend
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\seed_courses.py
uvicorn app.main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

## PowerShell first-time frontend setup

Second PowerShell window:

```powershell
cd .\frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

## Daily run

Backend terminal:

```powershell
cd .\backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Frontend terminal:

```powershell
cd .\frontend
npm run dev
```

---

## Testing reset

Delete learners/history/uploads but keep course catalog:

```powershell
cd .\backend
.\.venv\Scripts\Activate.ps1
python .\reset_test_data.py
```

Type:

```text
RESET
```

Full development reset:

```powershell
python .\reset_everything.py
```

then:

```powershell
python .\seed_courses.py
```

Do not use destructive resets in production.

---

## Business regression tests

Preserve these tests:

### A

```text
IGC PASS
```

Expected: IDP Entry lead + IDP recommendation.

### B

```text
IGC PASS
ID1 PASS
```

Expected: ID2 + ID3, no IDP Entry.

### C

```text
ID2 PASS
```

Expected: ID1 + ID3.

### D

```text
ID3 PASS
```

Expected: ID1 + ID2.

### E

```text
ID1 PASS
ID3 PASS
```

Expected: ID2 only.

### F

```text
ID1 PASS
ID2 ENROLLED
```

Expected: ID3 only.

### G

```text
ID1 PASS
ID2 PASS
ID3 PASS
```

Expected: no current ID-course opportunity.

---

## Current limitations / sensible next updates

Good next tasks:

1. update `idp.py` from a real IDP spreadsheet
2. row-level import error reporting
3. pagination
4. opportunity filters
5. CRM notes/contact history
6. follow-up workflow
7. recommendation shown/contacted/converted tracking
8. Alembic database migrations
9. automated tests
10. authentication and roles

Do not add ML yet unless explicitly requested.

---

# Full CRM expansion (September 2026)

## Workspace separation

The authenticated application now has three connected workspaces selected from the sidebar:

- **Main CRM (`/crm`)** manages people who have enquired but may not yet be registered.
- **Learners CRM (`/learners-crm`)** is the new central workspace intended for uploading and managing all registered learners.
- **Upsell CRM (`/upsell`)** preserves the original registered-learner and course-opportunity system.

Learners CRM now contains an active learner-import foundation:

- `/learners-crm` — overview with unique learner, enrolment, active, completed, and Main CRM match totals.
- `/learners-crm/uploads` — admin-only new/update learner Excel imports with upload references.

Learner upload columns are `enrolment_id`, `learner_name`, `email_id`, `course_name`, `enrolment_date`, `start_date`, `completion_date`, and `completion_status`. A person is uniquely identified by normalized `email_id`; `enrolment_id` uniquely identifies each course enrolment, allowing one learner to have multiple courses. New files receive an `LCRM-...` upload number, and Update mode replaces the selected upload transactionally.

Learners CRM stores data separately in `learners_crm_profiles` and `learners_crm_enrollments`. This avoids treating an enrolment ID as a person ID and keeps the existing Upsell CRM course-history tables intact.

Main CRM routes:

- `/crm` — enquiry overview and headline metrics.
- `/crm/leads` — searchable lead pipeline with status and counselor assignment.
- `/crm/leads/:leadId` — complete enquiry/call/campaign lifecycle.
- `/crm/campaigns` — campaigns sent and campaign replies.
- `/crm/analytics` — source, conversion, registration, and assignment reporting.
- `/crm/uploads` — admin-only new/update Excel uploads.
- `/crm/mapping` — admin-only counselor-account and territory mapping.

Upsell routes are the original routes prefixed with `/upsell`, including overview, learners, opportunities, campaigns, analytics, and uploads.

## Main CRM identity and learner matching

Main CRM leads do not have learner numbers. The importer normalizes and matches by either:

- lowercase, trimmed email; or
- phone digits normalized to the final ten digits.

When a Main CRM lead matches an Upsell CRM learner by email or phone, `matched_learner_number` connects the two profiles. The Main CRM lifecycle page then links to the registered learner's Upsell lifecycle.

## Canonical customer connection across all CRMs

All three workspaces now connect through a shared customer identity layer:

- `customers` represents one real person independently of CRM workflow.
- `customer_identities` stores normalized `EMAIL` and `PHONE` values with a uniqueness rule per identity type.
- `main_crm_leads.customer_id` links enquiries and their activity timeline.
- `learners_crm_profiles.customer_id` links the registered learner and all enrolments.
- `learners.customer_id` links external-board IGC/IDP learner numbers and result history.

Matching checks normalized email first and then normalized phone. A customer may have multiple course enrolments and may also have one or more external-board learner records. `enrolment_id` remains a course-enrolment key and is never treated as a person identifier. A board `learner_number` remains specific to IGC/IDP assessment data and is never manufactured for other learners.

When a Learners CRM upload or an Upsell board-result upload resolves to the same customer as a Main CRM enquiry, that enquiry is automatically set to `CONVERTED`. Board-result imports also populate `matched_learner_number`, enabling the existing link to the Upsell learner journey. No new recommendation logic is inferred from general enrolments yet; future course and level mappings can extend the rule engine.

Upsell imports must flush the external-board `learners` row before setting `main_crm_leads.matched_learner_number`. This ordering is required by the foreign key and makes upload order across Main CRM, Learners CRM, and Upsell CRM independent.

Existing unlinked rows are backfilled idempotently during the current startup compatibility migration. The schema diagram is stored at `docs/connected-crm-schema.png`; its reproducible drawing script is `docs/generate_schema_diagram.ps1`.

## Main CRM upload types

Every new file receives one upload-level reference such as `CRM-20260901-A1B2`. This reference belongs to the entire Excel file, not an individual row.

The Data Uploads page supports:

- **New upload** — creates a new unique upload reference.
- **Update upload** — selects an existing reference and replaces its imported lifecycle data. Validation occurs transactionally so a failed replacement does not intentionally discard the previous valid import.

Supported upload types:

1. **Info email leads (`INFO_EMAIL_LEADS`)**
   - Umbrella source for web enquiries, live chat, landing pages, and social-media leads.
   - The row's `source` value retains the specific sub-source.
   - Core columns: `full_name`, `email`, `phone_number`, `whatsapp_number`, `source`, `course`, `region`, `age`, `status_of_lead`, `counselor`, `sales_owner`, `counsilor_email`, `note`.
2. **Direct calls (`DIRECT_CALLS`)**
   - Stores call enquiries as lifecycle activities.
   - Supports date, full name (including the supplied `Full Nmae` spelling), email, phone, WhatsApp, source, country/region, course, service type, status, counselor, counselor email, call type, test status, comment, and follow-up date.
3. **Campaign replies (`CAMPAIGN_REPLIES`)**
   - Columns: `date`, `email`, `campaign_type`, `course`, `full_user_reply`, `campaign name`, `campaign description`.
   - Appends the full reply to the matching email's lifecycle.
4. **Campaign data (`CAMPAIGN_DATA`)**
   - Columns: `date`, `email`, `campaign_type`, `campaign name`, `campaign description`, `course_campaign`.
   - Records marketing sent to the matching lead. Email is supported now; the channel model can later support WhatsApp and LinkedIn.

Original row data is retained in `main_crm_activities.raw_data` so more source-specific fields can be exposed later without losing the imported values.

## Main CRM data model

- `main_crm_leads` stores the current unified lead/contact profile, normalized identity fields, ownership, source, status, and optional learner link.
- `main_crm_activities` stores dated enquiries, direct calls, campaigns sent, and campaign replies.
- `upload_batches.unique_number` stores the upload-level reference used for replacement imports.
- `users` now includes `email`, `country`, and `region` for counselor mapping.

## Lead workflow

- Admins see all leads and may assign counselors.
- Counselors see only leads assigned to them.
- Lead status can be changed from the pipeline.
- Selecting a counselor displays the counselor's mapped email.
- Assignment applies the counselor's region to the lead; when region is blank, country is used as the fallback territory.
- Supported frontend statuses currently include New, In contact, Follow up, Converted, and Rejected.

## Counselor mapping

The Mapping page can create counselors and update their display name, email, country, region, and password. Usernames are fixed after creation. Passwords are securely hashed and never returned to the frontend. Changing a counselor password invalidates that counselor's existing sessions.

The agreed production-shaped test accounts are seeded by:

```powershell
cd backend
python seed_crm_counselors.py
```

The script is idempotent and creates or updates 17 counselor accounts. All currently use the temporary password `test1234`; regions are blank and countries are populated. `A.Pandiyan` uses the safely normalized username `counselor_a_pandiyan`; all others follow `counselor_{lowercase_name}`.

## Database initialization

The application currently uses `Base.metadata.create_all()` plus small startup column checks for compatibility with the existing database. Added tables are created on backend startup, and the `users.country`, `users.region`, `users.email`, and `upload_batches.unique_number` columns are added when absent. Alembic remains the recommended future production migration system.

---

# Quick prompt for the next chat

Copy/paste:

> I am continuing a Learning CRM project. I uploaded `learning-crm.zip` and `HANDOFF.md`. Read `HANDOFF.md` first and inspect the repository before changing anything. The stack is React + Vite, FastAPI, SQLAlchemy and PostgreSQL. Stage 1 uses learner_number as the learner key. IGC is a course; IDP is a program containing independent courses ID1, ID2 and ID3. Recommendation/opportunity logic is rule-based and the single source of truth is `backend/app/services/course_rules.py`. Course-specific Excel importers are separate files under `backend/app/services/importers/` and are auto-discovered. Preserve all dated learner history. For every requested code change, explain what changed and why, then give the full replacement content of every changed file and mention any DB/setup step. Do not redesign working architecture unless necessary. First summarize your understanding of the current repository in 8–12 bullets, then wait for my requested change.
