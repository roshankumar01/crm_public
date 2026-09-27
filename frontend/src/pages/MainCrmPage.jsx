import { useEffect, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { assignMainCrmLead, getCounselors, getMainCrmLeads, getMainCrmSummary, updateMainCrmLeadStatus } from "../api";
import { useAuth } from "../context/AuthContext.jsx";

const SOURCES = [["ALL", "All leads"], ["INFO_EMAIL_LEADS", "Info email leads"], ["LIVE_ONLINE_LEADS", "Live online leads"], ["DIRECT_CALLS", "Direct calls"]];
const STATUSES = [["NEW", "New"], ["NO_RESPONSE", "No Response"], ["FOLLOW_UP", "Follow up"], ["LATER", "Later"], ["CONVERTED", "Converted"], ["CALL_ME_LATER", "Call me later"], ["GOOD", "Good"], ["NOT_INTERESTED", "Not interested"], ["INVALID", "Invalid"], ["HOT", "Hot"], ["OTHERS", "Others"], ["BLANK", "blank"]];
const LEGACY_STATUSES = [["IN_CONTACT", "In contact"], ["REJECTED", "Rejected"]];
function optionsFor(lead) {
  const options = lead.is_migrated ? STATUSES : [...STATUSES, ...LEGACY_STATUSES];
  return options.some(([value]) => value === lead.status_of_lead)
    ? options : [...options, [lead.status_of_lead, lead.status_of_lead.replaceAll("_", " ")]];
}

export default function MainCrmPage() {
  const { user } = useAuth();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const isAdmin = user?.role === "ADMIN";
  const [result, setResult] = useState(null);
  const [summary, setSummary] = useState(null);
  const [counselors, setCounselors] = useState([]);
  const activeSource = SOURCES.some(([value]) => value === params.get("source")) ? params.get("source") : "ALL";
  const search = params.get("q") || "";
  const page = Math.max(1, Number.parseInt(params.get("page"), 10) || 1);
  const [searchInput, setSearchInput] = useState(search);
  const [refreshKey, setRefreshKey] = useState(0);
  const [saving, setSaving] = useState(null);
  const [message, setMessage] = useState("");

  useEffect(() => { setSearchInput(search); }, [search]);

  function submitSearch(event) {
    event.preventDefault();
    const term = searchInput.trim();
    if (term === search) return;
    setParams(current => {
      const next = new URLSearchParams(current);
      if (term) next.set("q", term); else next.delete("q");
      next.delete("page");
      return next;
    });
  }

  function selectSource(source) {
    setParams(current => {
      const next = new URLSearchParams(current);
      if (source === "ALL") next.delete("source"); else next.set("source", source);
      next.delete("page");
      return next;
    });
  }

  function selectPage(nextPage) {
    setParams(current => {
      const next = new URLSearchParams(current);
      if (nextPage <= 1) next.delete("page"); else next.set("page", String(nextPage));
      return next;
    });
  }

  useEffect(() => {
    let cancelled = false;
    getMainCrmLeads({ page, sourceCategory: activeSource, search })
      .then(data => { if (!cancelled) { setResult(data); setMessage(""); } })
      .catch(error => { if (!cancelled) setMessage(error.message); });
    return () => { cancelled = true; };
  }, [page, activeSource, search, refreshKey]);

  useEffect(() => {
    let cancelled = false;
    getMainCrmSummary().then(data => { if (!cancelled) setSummary(data); })
      .catch(error => { if (!cancelled) setMessage(error.message); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  useEffect(() => {
    if (!isAdmin) return;
    getCounselors().then(setCounselors).catch(error => setMessage(error.message));
  }, [isAdmin]);

  async function changeStatus(id, status) {
    try { setSaving(id); await updateMainCrmLeadStatus(id, status); setRefreshKey(value => value + 1); }
    catch (error) { setMessage(error.message); }
    finally { setSaving(null); }
  }
  async function changeCounselor(id, value) {
    try { setSaving(id); await assignMainCrmLead(id, value ? Number(value) : null); setRefreshKey(current => current + 1); }
    catch (error) { setMessage(error.message); }
    finally { setSaving(null); }
  }

  if (!result && !message) return <div className="page"><div className="loading-state"><span />Loading Main CRM...</div></div>;
  const leads = result?.items || [];
  return <div className="page main-crm-page">
    <div className="page-header simple-header"><div><div className="eyebrow">MAIN CRM</div><h1>Enquiry leads</h1><p className="page-description">Manage every enquiry before registration and connect converted people to their learner lifecycle.</p></div><div className="opportunity-count">{(summary?.total ?? result?.total ?? 0).toLocaleString()}<span>total leads</span></div></div>
    {message && <div className="upload-message page-message">{message}</div>}
    <div className="main-crm-source-tabs">{SOURCES.map(([value, label]) => <button key={value} className={activeSource === value ? "source-tab active" : "source-tab"} onClick={() => selectSource(value)}>{label}<span>{value === "ALL" ? summary?.total ?? "…" : summary?.source_category_counts?.[value] ?? "…"}</span></button>)}</div>
    <div className="toolbar"><form className="main-crm-search-form" onSubmit={submitSearch}><input className="search-input" value={searchInput} onChange={event => setSearchInput(event.target.value)} placeholder="Search name, email, phone, course or source" aria-label="Search leads" maxLength={320} /><button className="primary-button" type="submit">Search</button></form><span className="filter-count">{(result?.total ?? 0).toLocaleString()} matching leads</span></div>
    <div className="table-card pipeline-table"><table className="main-leads-table"><thead><tr><th>Lead</th><th>Source</th><th>Course / Region</th><th>Status</th><th>Counselor</th><th>Profile</th></tr></thead><tbody>{leads.map(lead => <tr key={lead.id}>
      <td><div className="learner-cell"><div className="avatar">{lead.full_name?.[0]?.toUpperCase()}</div><div><Link className="profile-name-link" to={`/crm/leads/${lead.id}`} state={{ from: location.pathname + location.search }}>{lead.full_name}</Link><div className="small-muted">{lead.email || "No email"}</div><div className="small-muted">{lead.phone_number || "No phone"}</div></div></div></td>
      <td><strong>{lead.source || "—"}</strong><div className="small-muted">{SOURCES.find(item => item[0] === lead.source_category)?.[1]}</div>{lead.is_migrated && <div className="small-muted">Migrated</div>}</td>
      <td><strong>{lead.course || "—"}</strong><div className="small-muted">{lead.region || "No region"}{lead.age ? ` · Age ${lead.age}` : ""}</div></td>
      <td><select className="compact-select" value={lead.status_of_lead} disabled={saving === lead.id} onChange={event => changeStatus(lead.id, event.target.value)}>{optionsFor(lead).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></td>
      <td>{isAdmin ? <select className="compact-select" value={lead.assigned_to_user_id || ""} disabled={saving === lead.id} onChange={event => changeCounselor(lead.id, event.target.value)}><option value="">Unassigned</option>{counselors.map(counselor => <option key={counselor.id} value={counselor.id}>{counselor.display_name}</option>)}</select> : <strong>{lead.counselor || "Unassigned"}</strong>}<div className="small-muted">{lead.counselor_email || "No counselor email"}</div></td>
      <td><Link className="text-link" to={`/crm/leads/${lead.id}`} state={{ from: location.pathname + location.search }}>View full profile →</Link>{lead.matched_learner_number && <div className="small-muted">Registered learner #{lead.matched_learner_number}</div>}</td>
    </tr>)}</tbody></table>{!leads.length && <div className="table-message">No leads match these filters.</div>}</div>
    {result && <nav className="crm-pagination" aria-label="Lead pages"><button className="secondary-button" disabled={page <= 1} onClick={() => selectPage(page - 1)}>← Previous</button><span>Page {result.page} of {result.pages}</span><button className="secondary-button" disabled={page >= result.pages} onClick={() => selectPage(page + 1)}>Next →</button></nav>}
  </div>;
}
