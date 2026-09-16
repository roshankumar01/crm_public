import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getLearnersCrmOverview } from "../api";
import { useAuth } from "../context/AuthContext.jsx";

export default function LearnersCrmOverviewPage() {
  const { user } = useAuth(); const [summary,setSummary]=useState(null); const [error,setError]=useState("");
  useEffect(()=>{getLearnersCrmOverview().then(setSummary).catch(e=>setError(e.message))},[]);
  if(!summary)return <div className="page"><div className="loading-state"><span/>{error||"Loading learner overview..."}</div></div>;
  return <div className="page"><div className="page-header simple-header"><div><div className="eyebrow">LEARNERS CRM</div><h1>Learner overview</h1><p className="page-description">The central workspace for registered learners and their course enrolments.</p></div>{user?.role==="ADMIN"&&<Link className="primary-button" to="/learners-crm/uploads">Open data uploads →</Link>}</div><div className="simple-stats"><div className="simple-stat main"><span>Total learners</span><strong>{summary.total_learners}</strong><small>Unique normalized email addresses</small></div><div className="simple-stat"><span>Course enrolments</span><strong>{summary.total_enrolments}</strong><small>Unique enrolment IDs</small></div><div className="simple-stat"><span>Active enrolments</span><strong>{summary.active}</strong><small>Currently active or in progress</small></div><div className="simple-stat"><span>Completed</span><strong>{summary.completed}</strong><small>Completed or passed courses</small></div></div><div className="dashboard-panel"><div><div className="eyebrow">CONNECTED LIFECYCLE</div><h2>{summary.matched_enquiries} learners match Main CRM enquiries</h2><p>Matching currently uses normalized email so enquiry history can later connect to learner and upsell activity.</p></div></div></div>;
}
