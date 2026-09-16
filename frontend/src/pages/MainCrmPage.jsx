import { useCallback, useEffect, useMemo, useState } from "react";
import { assignMainCrmLead, getCounselors, getMainCrmLeads, updateMainCrmLeadStatus } from "../api";
import { useAuth } from "../context/AuthContext.jsx";

const SOURCES = [["ALL", "All leads"], ["INFO_EMAIL_LEADS", "Info email leads"], ["LIVE_ONLINE_LEADS", "Live online leads"], ["DIRECT_CALLS", "Direct calls"]];
const STATUSES = [["NEW", "New"], ["IN_CONTACT", "In contact"], ["FOLLOW_UP", "Follow up"], ["CONVERTED", "Converted"], ["REJECTED", "Rejected"]];

export default function MainCrmPage() {
  const { user } = useAuth(); const isAdmin = user?.role === "ADMIN";
  const [leads, setLeads] = useState([]); const [counselors, setCounselors] = useState([]);
  const [activeSource, setActiveSource] = useState("ALL"); const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(null);
  const [message, setMessage] = useState("");
  const load = useCallback(async () => { try { const [leadRows, people] = await Promise.all([getMainCrmLeads(), isAdmin ? getCounselors() : Promise.resolve([])]); setLeads(leadRows); setCounselors(people); } catch (e) { setMessage(e.message); } finally { setLoading(false); } }, [isAdmin]);
  useEffect(() => { load(); }, [load]);
  const visible = useMemo(() => { const query = search.trim().toLowerCase(); return leads.filter(lead => (activeSource === "ALL" || lead.source_category === activeSource) && (!query || `${lead.full_name} ${lead.email || ""} ${lead.phone_number || ""} ${lead.course || ""} ${lead.source || ""}`.toLowerCase().includes(query))); }, [leads, activeSource, search]);
  async function changeStatus(id, status) { try { setSaving(id); await updateMainCrmLeadStatus(id, status); await load(); } catch (e) { setMessage(e.message); } finally { setSaving(null); } }
  async function changeCounselor(id, value) { try { setSaving(id); await assignMainCrmLead(id, value ? Number(value) : null); await load(); } catch (e) { setMessage(e.message); } finally { setSaving(null); } }
  if (loading) return <div className="page"><div className="loading-state"><span/>Loading Main CRM...</div></div>;
  return <div className="page main-crm-page">
    <div className="page-header simple-header"><div><div className="eyebrow">MAIN CRM</div><h1>Enquiry leads</h1><p className="page-description">Manage every enquiry before registration and connect converted people to their learner lifecycle.</p></div><div className="opportunity-count">{leads.length}<span>total leads</span></div></div>
    {message && <div className="upload-message page-message">{message}</div>}
    <div className="main-crm-source-tabs">{SOURCES.map(([value, label]) => <button key={value} className={activeSource === value ? "source-tab active" : "source-tab"} onClick={() => setActiveSource(value)}>{label}<span>{value === "ALL" ? leads.length : leads.filter(l => l.source_category === value).length}</span></button>)}</div>
    <div className="toolbar"><input className="search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, email, phone, course or source"/></div>
    <div className="table-card pipeline-table"><table className="main-leads-table"><thead><tr><th>Lead</th><th>Source</th><th>Course / Region</th><th>Status</th><th>Counselor</th><th>Lifecycle</th></tr></thead><tbody>{visible.map(lead => <tr key={lead.id}><td><div className="learner-cell"><div className="avatar">{lead.full_name?.[0]?.toUpperCase()}</div><div><strong>{lead.full_name}</strong><div className="small-muted">{lead.email || "No email"}</div><div className="small-muted">{lead.phone_number || "No phone"}</div></div></div></td><td><strong>{lead.source || "—"}</strong><div className="small-muted">{SOURCES.find(item => item[0] === lead.source_category)?.[1]}</div></td><td><strong>{lead.course || "—"}</strong><div className="small-muted">{lead.region || "No region"}{lead.age ? ` · Age ${lead.age}` : ""}</div></td><td><select className="compact-select" value={lead.status_of_lead} disabled={saving === lead.id} onChange={e => changeStatus(lead.id, e.target.value)}>{STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></td><td>{isAdmin ? <select className="compact-select" value={lead.assigned_to_user_id || ""} disabled={saving === lead.id} onChange={e => changeCounselor(lead.id, e.target.value)}><option value="">Unassigned</option>{counselors.map(c => <option key={c.id} value={c.id}>{c.display_name}</option>)}</select> : <strong>{lead.counselor || "Unassigned"}</strong>}<div className="small-muted">{lead.counselor_email || "No counselor email"}</div></td><td><a className="text-link" href={`/crm/leads/${lead.id}`}>View lifecycle →</a>{lead.matched_learner_number&&<div className="small-muted">Registered learner #{lead.matched_learner_number}</div>}</td></tr>)}</tbody></table>{visible.length === 0 && <div className="table-message">No leads found in this source.</div>}</div>
  </div>;
}
