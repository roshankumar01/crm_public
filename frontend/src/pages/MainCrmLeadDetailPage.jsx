import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getMainCrmLead } from "../api";
import CustomerLifecycle from "../components/CustomerLifecycle.jsx";

const activityLabels = { ENQUIRY: "Enquiry received", DIRECT_CALL: "Direct call", CAMPAIGN_SENT: "Campaign sent", CAMPAIGN_REPLY: "Campaign reply", MIGRATION: "Old CRM migration" };
const statusLabels = { NEW: "New", NO_RESPONSE: "No Response", FOLLOW_UP: "Follow up", LATER: "Later", CONVERTED: "Converted", CALL_ME_LATER: "Call me later", GOOD: "Good", NOT_INTERESTED: "Not interested", INVALID: "Invalid", HOT: "Hot", OTHERS: "Others", BLANK: "blank", IN_CONTACT: "In contact", REJECTED: "Rejected" };
const legacyLabels = {
  name: "Name", salesowner: "Sales owner", owneremail: "Owner email", mobile: "Mobile",
  coursename: "Course name", age: "Age", statusoflead: "Original lead status", regions: "Regions",
  lastassignedat: "Last assigned at", firstassignedat: "First assigned at", createdat: "Created at",
  updatedat: "Updated at", createdby: "Created by", updatedby: "Updated by",
  otherphonenumbers: "Other phone numbers", source: "Source", recentnote: "Recent note",
  email: "Email", emailids: "Email IDs", message: "Message",
};

function Field({ label, value }) {
  return <div className="profile-field"><span>{label}</span><strong>{value ?? "Not provided"}</strong></div>;
}

export default function MainCrmLeadDetailPage() {
  const { leadId } = useParams();
  const location = useLocation();
  const backToLeads = location.state?.from || "/crm/leads";
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { getMainCrmLead(leadId).then(setData).catch(requestError => setError(requestError.message)); }, [leadId]);
  if (error) return <div className="page"><Link to={backToLeads} className="back-link">← Back to leads</Link><div className="empty-card">{error}</div></div>;
  if (!data) return <div className="page"><div className="loading-state"><span />Loading lead...</div></div>;
  const { lead, activities } = data;
  return <div className="page profile-detail-page">
    <Link to={backToLeads} className="back-link">← Back to leads</Link>
    <div className="profile-hero premium-profile"><div className="profile-avatar">{lead.full_name?.[0]?.toUpperCase()}</div><div className="profile-main"><div className="eyebrow">LEAD PROFILE</div><h1>{lead.full_name}</h1><div className="profile-number">{lead.source || lead.source_category} · {statusLabels[lead.status_of_lead] || lead.status_of_lead}{lead.is_migrated && " · Migrated"}</div></div><div className="profile-contact"><div><span>Email</span><strong>{lead.email || "Not provided"}</strong></div><div><span>Phone</span><strong>{lead.phone_number || "Not provided"}</strong></div></div></div>
    <div className="profile-summary-grid"><div className="profile-summary-card"><span>Lead status</span><strong className="summary-text">{statusLabels[lead.status_of_lead] || lead.status_of_lead}</strong></div><div className="profile-summary-card"><span>Source</span><strong className="summary-text">{lead.source || "Not provided"}</strong></div><div className="profile-summary-card"><span>Activity records</span><strong>{activities.length}</strong></div></div>
    <CustomerLifecycle lifecycle={data.lifecycle} />
    <section className="profile-section"><div className="section-heading"><div><div className="eyebrow">CURRENT RECORD</div><h2>Lead details</h2></div></div><div className="profile-fields"><Field label="Full name" value={lead.full_name} /><Field label="Email" value={lead.email} /><Field label="Phone number" value={lead.phone_number} /><Field label="WhatsApp number" value={lead.whatsapp_number} /><Field label="Course" value={lead.course} /><Field label="Region" value={lead.region} /><Field label="Country" value={lead.country} /><Field label="Age" value={lead.age} /><Field label="Source category" value={lead.source_category?.replaceAll("_", " ")} /><Field label="Sales owner" value={lead.sales_owner} /><Field label="Assigned counselor" value={lead.counselor} /><Field label="Counselor email" value={lead.counselor_email} /><Field label="Lead created" value={lead.created_at && new Date(lead.created_at).toLocaleString()} /><Field label="Last updated" value={lead.is_migrated ? lead.migration_updated_at : (lead.updated_at && new Date(lead.updated_at).toLocaleString())} /></div>{lead.notes && <div className="profile-note"><strong>Latest note</strong><p>{lead.notes}</p></div>}</section>
    {lead.matched_learner_number && <div className="dashboard-panel section-panel"><div><div className="eyebrow">REGISTERED CUSTOMER</div><h2>Upsell lifecycle available</h2><p>This enquiry matches a registered learner.</p></div><Link className="primary-button" to={`/upsell/learners/${lead.matched_learner_number}`}>Open learner #{lead.matched_learner_number} →</Link></div>}
    <section className="profile-section"><div className="section-heading"><div><div className="eyebrow">COMPLETE HISTORY</div><h2>Lead activity</h2></div></div><div className="journey">{activities.map((item, index) => <div className="journey-item" key={item.id}><div className="journey-rail"><div className="journey-dot pass">✓</div>{index < activities.length - 1 && <div className="journey-line" />}</div><div className="journey-card"><div className="journey-card-header"><div><div className="journey-date">{item.activity_date || new Date(item.created_at).toLocaleDateString()}</div><h3>{activityLabels[item.activity_type] || item.activity_type}</h3></div>{item.channel && <span className="channel-pill email">{item.channel}</span>}</div>{item.campaign_name && <p><strong>{item.campaign_name}</strong></p>}{item.campaign_description && <p>{item.campaign_description}</p>}{item.course && <p>Course: <strong>{item.course}</strong></p>}{item.full_user_reply && <p><strong>Message:</strong> {item.full_user_reply}</p>}{item.notes && <p><strong>Note:</strong> {item.notes}</p>}{item.raw_data && Object.keys(item.raw_data).length > 0 && <details className="profile-original-data"><summary>{item.activity_type === "MIGRATION" ? "View original CRM row" : "View uploaded row"}</summary><div className="profile-fields">{Object.entries(item.raw_data).map(([key, value]) => <Field key={key} label={legacyLabels[key] || key.replaceAll("_", " ")} value={value} />)}</div></details>}</div></div>)}{!activities.length && <div className="empty-card">No activity has been uploaded for this lead.</div>}</div></section>
  </div>;
}
