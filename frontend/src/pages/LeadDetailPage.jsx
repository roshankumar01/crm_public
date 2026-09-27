import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { addLeadActivity, assignLead, getCounselors, getLead, updateLeadStatus } from "../api";
import { useAuth } from "../context/AuthContext.jsx";

const STATUS_OPTIONS = [
  ["NEW", "New"],
  ["IN_CONTACT", "In contact"],
  ["REJECTED", "Rejected the offer"],
  ["CONVERTED", "Converted"],
];

const ACTIVITY_OPTIONS = [
  ["EMAIL_CAMPAIGN", "Email campaign"],
  ["WHATSAPP_CAMPAIGN", "WhatsApp campaign"],
  ["CALL", "Call"],
  ["NOTE", "Note"],
];

function displayActivity(value) {
  return value?.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
}

export default function LeadDetailPage() {
  const { leadId } = useParams();
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMIN";
  const [data, setData] = useState(null);
  const [counselors, setCounselors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activityType, setActivityType] = useState("EMAIL_CAMPAIGN");
  const [campaignName, setCampaignName] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [leadData, counselorData] = await Promise.all([
        getLead(leadId),
        isAdmin ? getCounselors() : Promise.resolve([]),
      ]);
      setData(leadData);
      setCounselors(counselorData);
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [leadId, isAdmin]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [load]);

  async function changeStatus(status) {
    try {
      setSaving(true);
      await updateLeadStatus(leadId, status);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function changeAssignment(value) {
    try {
      setSaving(true);
      await assignLead(leadId, value ? Number(value) : null);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function submitActivity(event) {
    event.preventDefault();
    try {
      setSaving(true);
      setError("");
      await addLeadActivity(leadId, {
        activity_type: activityType,
        campaign_name: campaignName || null,
        notes: notes || null,
      });
      setCampaignName("");
      setNotes("");
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="page">Loading lead...</div>;
  if (error && !data) return <div className="page"><div className="empty-card">{error}</div></div>;
  if (!data?.lead || !data?.learner) return <div className="page">Lead not found.</div>;

  const { lead, learner } = data;
  const needsCampaignName = activityType === "EMAIL_CAMPAIGN" || activityType === "WHATSAPP_CAMPAIGN";

  return <div className="page">
    <Link to="/upsell/opportunities" className="back-link">← Back to leads</Link>
    <div className="profile-hero"><div className="profile-avatar">{learner.name?.charAt(0)?.toUpperCase()}</div><div className="profile-main"><div className="eyebrow">LEAD #{lead.id}</div><h1>{learner.name}</h1><div className="profile-number">{learner.learner_number ? `Learner #${learner.learner_number} · ` : ""}Target {lead.target_code}{lead.stage ? ` · Stage ${lead.stage}` : ""}</div></div><div className="profile-contact"><div><span>Email</span><strong>{learner.email_id || "—"}</strong></div><div><span>Phone</span><strong>{learner.contact_number || "—"}</strong></div><div><span>Trigger</span><strong>{lead.trigger_date || "—"}</strong></div></div></div>
    {error && <div className="form-error page-message">{error}</div>}

    <div className="crm-grid">
      <section>
        <div className="crm-card">
          <div className="section-heading"><div><div className="eyebrow">WORKFLOW</div><h2>Lead status</h2></div></div>
          <div className="form-grid two-col">
            <div><label>Status</label><select value={lead.status} disabled={saving} onChange={e => changeStatus(e.target.value)}>{STATUS_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
            <div><label>Counselor</label>{isAdmin ? <select value={lead.assigned_to_user_id || ""} disabled={saving} onChange={e => changeAssignment(e.target.value)}><option value="">Unassigned</option>{counselors.map(c => <option key={c.id} value={c.id}>{c.display_name}</option>)}</select> : <div className="readonly-field">{lead.assigned_to_name || "Unassigned"}</div>}</div>
          </div>
          <div className="lead-meta"><span>Current rule opportunity: <strong>{lead.is_active ? "Yes" : "No"}</strong></span><span>Assigned: <strong>{lead.assigned_at ? new Date(lead.assigned_at).toLocaleString() : "—"}</strong></span></div>
          <Link className="secondary-button" to={learner.customer_id ? `/upsell/contacts/${learner.customer_id}` : `/upsell/learners/${learner.learner_number}`}>View learner lifecycle →</Link>
        </div>

        <form className="crm-card" onSubmit={submitActivity}>
          <div className="section-heading"><div><div className="eyebrow">CONTACT HISTORY</div><h2>Log counselor activity</h2></div></div>
          <div className="form-grid two-col"><div><label>Activity</label><select value={activityType} onChange={e => setActivityType(e.target.value)}>{ACTIVITY_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>{needsCampaignName && <div><label>Campaign name</label><input value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="e.g. ID2 August follow-up" required /></div>}</div>
          <label>Notes</label><textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="What happened in the conversation or campaign?" rows="4" />
          <button className="primary-button" type="submit" disabled={saving}>{saving ? "Saving..." : "Save activity"}</button>
        </form>

        <div className="section-heading journey-heading"><div><div className="eyebrow">CRM HISTORY</div><h2>Lead activity timeline</h2></div></div>
        <div className="activity-list">{data.activities.map(activity => <div className="activity-card" key={activity.id}><div><strong>{displayActivity(activity.activity_type)}</strong>{activity.campaign_name && <span className="campaign-chip">{activity.campaign_name}</span>}</div><div className="small-muted">{new Date(activity.created_at).toLocaleString()} · {activity.user_name}</div>{activity.notes && <p>{activity.notes}</p>}</div>)}{data.activities.length === 0 && <div className="empty-card">No CRM activity logged yet.</div>}</div>
      </section>

      <aside>
        <div className="side-card"><div className="eyebrow">ADMIN CAMPAIGNS</div><h3>Campaigns linked to learner</h3>{data.campaigns.length === 0 ? <p className="muted">No uploaded campaigns.</p> : <div className="campaign-list">{data.campaigns.map(campaign => <div className="campaign-row" key={campaign.id}><strong>{campaign.campaign_name}</strong><span>{new Date(campaign.created_at).toLocaleDateString()}</span></div>)}</div>}</div>
      </aside>
    </div>
  </div>;
}
