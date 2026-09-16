import { useEffect, useState } from "react";
import { getMainCrmCampaignActivities } from "../api";

export default function MainCrmCampaignsPage() {
  const [items,setItems]=useState(null); const [error,setError]=useState("");
  useEffect(()=>{getMainCrmCampaignActivities().then(setItems).catch(e=>setError(e.message))},[]);
  if(!items)return <div className="page"><div className="loading-state"><span/>{error||"Loading campaigns..."}</div></div>;
  return <div className="page"><div className="page-header simple-header"><div><div className="eyebrow">MAIN CRM CAMPAIGNS</div><h1>Campaign lifecycle</h1><p className="page-description">Campaigns sent and full user replies, connected to each lead by normalized email.</p></div><div className="opportunity-count">{items.length}<span>activities</span></div></div><div className="table-card pipeline-table"><table><thead><tr><th>Date</th><th>Lead</th><th>Activity</th><th>Campaign</th><th>Course</th><th>Reply</th></tr></thead><tbody>{items.map(item=><tr key={item.id}><td>{item.activity_date||new Date(item.created_at).toLocaleDateString()}</td><td><strong>{item.lead_name}</strong><div className="small-muted">{item.lead_email}</div></td><td><span className={item.activity_type==="CAMPAIGN_REPLY"?"channel-pill whatsapp":"channel-pill email"}>{item.activity_type==="CAMPAIGN_REPLY"?"Reply":"Sent"}</span><div className="small-muted">{item.channel}</div></td><td><strong>{item.campaign_name||"—"}</strong><div className="small-muted">{item.campaign_description}</div></td><td>{item.course||"—"}</td><td>{item.full_user_reply||"—"}</td></tr>)}</tbody></table>{!items.length&&<div className="table-message">No campaign data or replies uploaded yet.</div>}</div></div>;
}
