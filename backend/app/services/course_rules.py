IGC_COURSE_CODE = "IGC"
IDP_COURSE_CODES = ("ID1", "ID2", "ID3")


def is_completed(record):
    if record.result:
        return record.result.strip().upper() == "PASS"

    return (
        record.enrollment_status is not None
        and record.enrollment_status.strip().upper() == "COMPLETED"
    )


def analyze_history(history_rows):
    activity_courses = set()
    completed_courses = set()
    completion_dates = {}

    for record, course in history_rows:
        code = course.code.strip().upper()
        activity_courses.add(code)

        if is_completed(record):
            completed_courses.add(code)
            previous = completion_dates.get(code)
            if previous is None or record.event_date > previous:
                completion_dates[code] = record.event_date

    return {
        "activity_courses": activity_courses,
        "completed_courses": completed_courses,
        "completion_dates": completion_dates,
    }


def latest_completion_date(course_codes, completion_dates):
    dates = [completion_dates[c] for c in course_codes if c in completion_dates]
    return max(dates) if dates else None


def build_learner_opportunities(history_rows):
    """Single source of truth for progression and opportunity rules."""
    analysis = analyze_history(history_rows)
    activity = analysis["activity_courses"]
    completed = analysis["completed_courses"]
    completion_dates = analysis["completion_dates"]
    opportunities = []

    # IGC PASS/complete + no ID course activity -> IDP Entry lead.
    has_idp_activity = any(code in activity for code in IDP_COURSE_CODES)
    if IGC_COURSE_CODE in completed and not has_idp_activity:
        opportunities.append({
            "key": "IDP_ENTRY",
            "opportunity_type": "PROGRAM_ENTRY",
            "target_code": "IDP",
            "target_name": "IDP Programme",
            "trigger_courses": ["IGC"],
            "trigger_date": completion_dates.get("IGC"),
            "reason": "Learner completed IGC and has not yet entered ID1, ID2 or ID3.",
            "priority": 1,
        })

    # Any completed ID course makes all other never-entered ID courses opportunities.
    completed_id_courses = {code for code in IDP_COURSE_CODES if code in completed}
    if completed_id_courses:
        for target in IDP_COURSE_CODES:
            if target in activity:
                continue

            triggers = sorted(completed_id_courses)
            opportunities.append({
                "key": target,
                "opportunity_type": "COURSE",
                "target_code": target,
                "target_name": target,
                "trigger_courses": triggers,
                "trigger_date": latest_completion_date(triggers, completion_dates),
                "reason": f"Learner completed {', '.join(triggers)} and has not yet enrolled in {target}.",
                "priority": 10,
            })

    return opportunities
