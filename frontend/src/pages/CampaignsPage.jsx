import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getCampaignHistory } from "../api";

function SimpleStat({ label, value, note }) { return <div className="simple-stat"><span>{label}</span><strong>{value ?? 0}</strong><small>{note}</small></div>; }

export default function CampaignsPage() {
  const [data, setData] = useState(null); const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [channel, setChannel] = useState("ALL"); const [search, setSearch] = useState("");
  useEffect(() => { getCampaignHistory().then(setData).catch(e => setError(e.message)).finally(() => setLoading(false)); }, []);
  const channels = useMemo(() => [...new Set((data?.items || []).map(item => item.channel))].sort(), [data]);
  const items = useMemo(() => (data?.items || []).filter(item => (channel === "ALL" || item.channel === channel) && (!search || `${item.campaign_name} ${item.learner_name} ${item.learner_number}`.toLowerCase().includes(search.toLowerCase()))), [data, channel, search]);
  if (loading) return <div className="page"><div className="loading-state"><span/>Loading campaigns…</div></div>;
  if (error) return <div className="page"><div className="empty-card">{error}</div></div>;
  return <div className="page campaigns-page">
    <div className="page-header simple-header"><div><div className="eyebrow">CAMPAIGNS SENT</div><h1>Campaign history</h1><p className="page-description">See which campaigns were sent, who received them, and when they were sent.</p></div></div>
    <div className="simple-stats"><SimpleStat label="Total sent" value={data.total_sent} note="All campaign records"/><SimpleStat label="Learners reached" value={data.learners_reached} note="Unique learners"/><SimpleStat label="Email" value={data.email_sent} note="Email campaigns"/><SimpleStat label="WhatsApp" value={data.whatsapp_sent} note="WhatsApp campaigns"/></div>
    <div className="toolbar campaign-toolbar"><input className="search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search campaign or learner"/><select className="compact-select" value={channel} onChange={e => setChannel(e.target.value)}><option value="ALL">All marketing types</option>{channels.map(value => <option value={value} key={value}>{value}</option>)}</select></div>
    <div className="table-card"><table><thead><tr><th>Campaign</th><th>Channel</th><th>Learner</th><th>Sent by</th><th>Date sent</th><th></th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><strong>{item.campaign_name}</strong>{item.notes && <div className="small-muted">{item.notes}</div>}</td><td><span className={`channel-pill ${item.channel.toLowerCase()}`}>{item.channel}</span></td><td><strong>{item.learner_name}</strong><div className="small-muted">#{item.learner_number}</div></td><td>{item.sent_by}</td><td>{new Date(item.sent_at).toLocaleString()}</td><td><Link className="text-link" to={`/upsell/learners/${item.learner_number}`}>View learner →</Link></td></tr>)}</tbody></table>{items.length === 0 && <div className="table-message">No campaigns match this filter.</div>}</div>
  </div>;
}
