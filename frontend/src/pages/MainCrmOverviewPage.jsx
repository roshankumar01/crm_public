import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMainCrmSummary } from "../api";
import { useAuth } from "../context/AuthContext.jsx";

const SOURCES = [
  ["INFO_EMAIL_LEADS", "Info email leads"],
  ["LIVE_ONLINE_LEADS", "Live online leads"],
  ["DIRECT_CALLS", "Direct calls"],
];

export default function MainCrmOverviewPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { getMainCrmSummary().then(setSummary).catch(requestError => setError(requestError.message)); }, []);
  if (!summary) return <div className="page"><div className="loading-state"><span />{error || "Loading overview..."}</div></div>;

  const count = status => summary.status_counts?.[status] || 0;

  return <div className="page">
    <div className="page-header simple-header"><div><div className="eyebrow">MAIN CRM OVERVIEW</div><h1>Enquiry performance</h1><p className="page-description">A simple view of incoming leads, counselor activity, and registrations.</p></div><Link className="primary-button" to="/crm/leads">View lead pipeline →</Link></div>
    <div className="simple-stats"><div className="simple-stat main"><span>Total enquiries</span><strong>{summary.total}</strong><small>Across every source</small></div><div className="simple-stat"><span>New</span><strong>{count("NEW")}</strong><small>Waiting for first contact</small></div><div className="simple-stat"><span>In progress</span><strong>{["IN_CONTACT", "NO_RESPONSE", "FOLLOW_UP", "LATER", "CALL_ME_LATER", "GOOD", "HOT"].reduce((total, status) => total + count(status), 0)}</strong><small>Active conversations</small></div><div className="simple-stat"><span>Registered</span><strong>{summary.registered}</strong><small>Matched to Upsell CRM</small></div></div>
    <div className="simple-dashboard-grid">
      <section className="feature-card"><div className="card-heading"><div><div className="eyebrow">LEAD SOURCES</div><h2>Where enquiries come from</h2></div></div><div className="plain-progress-list">{SOURCES.map(([value, label]) => { const total = summary.source_counts?.[value] || 0; return <div className="plain-progress" key={value}><div><span>{label}</span><strong>{total}</strong></div><div className="plain-progress-track"><i style={{ width: `${summary.total ? total / summary.total * 100 : 0}%`, background: "#7357ff" }} /></div></div>; })}</div></section>
      <section className="feature-card action-card"><div className="card-heading"><div><div className="eyebrow">NEXT STEPS</div><h2>Manage your CRM</h2></div></div><div className="action-list"><Link to="/crm/leads"><span>1</span><div><strong>Work the lead pipeline</strong><small>Assign counselors and update lead status</small></div><b>→</b></Link><Link to="/crm/analytics"><span>2</span><div><strong>Review analytics</strong><small>Compare source and conversion performance</small></div><b>→</b></Link>{user?.role === "ADMIN" && <Link to="/crm/uploads"><span>3</span><div><strong>Manage data uploads</strong><small>Create or replace an Excel upload</small></div><b>→</b></Link>}</div></section>
    </div>
  </div>;
}
