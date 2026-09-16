import { useEffect, useState } from "react";
import { getMainCrmUploads, uploadMainCrmLeads } from "../api";
import UploadReset from "../components/UploadReset.jsx";

const TYPES = [
  ["INFO_EMAIL_LEADS", "Info email leads", "Web enquiry, live chat, landing-page and social-media leads. The source column keeps the sub-source."],
  ["LIVE_ONLINE_LEADS", "Live online leads", "Online leads imported separately from the live-chat leads contained in Info email leads."],
  ["DIRECT_CALLS", "Direct calls", "Inbound and outbound call enquiries."],
  ["CAMPAIGN_REPLIES", "Campaign replies", "User replies to email campaigns, matched by normalized email."],
  ["CAMPAIGN_DATA", "Campaign data", "Marketing messages sent to leads, matched by normalized email."],
];

const COLUMNS = {
  INFO_EMAIL_LEADS: ["full_name", "email", "phone_number", "whatsapp_number", "source", "course", "region", "age", "status_of_lead", "counselor", "sales_owner", "counsilor_email", "note"],
  LIVE_ONLINE_LEADS: ["FULLNAME", "EMAIL", "PHONENUMBER", "WHATSAPPNUMBER", "SOURCE", "COURSE", "REGIONS", "COUNSILORNAME", "COUNTRY"],
  DIRECT_CALLS: ["date", "full_name", "email", "phone_number", "whatsapp_number", "source", "country/region", "course", "service_type", "status", "counselor", "counselor_email", "call_type", "test_status", "comment", "followup_date"],
  CAMPAIGN_REPLIES: ["date", "email", "campaign_type", "course", "full_user_reply", "campaign name", "campaign description"],
  CAMPAIGN_DATA: ["date", "email", "campaign_type", "campaign name", "campaign description", "course_campaign"],
};

const REQUIRED_COLUMNS = {
  INFO_EMAIL_LEADS: new Set(["full_name", "email", "phone_number", "source", "course"]),
  LIVE_ONLINE_LEADS: new Set(["FULLNAME", "EMAIL", "PHONENUMBER", "WHATSAPPNUMBER", "SOURCE", "COURSE", "REGIONS", "COUNSILORNAME", "COUNTRY"]),
  DIRECT_CALLS: new Set(["date", "full_name", "email", "phone_number", "course"]),
  CAMPAIGN_REPLIES: new Set(["date", "email", "campaign_type", "course", "full_user_reply", "campaign name", "campaign description"]),
  CAMPAIGN_DATA: new Set(["date", "email", "campaign_type", "campaign name", "campaign description", "course_campaign"]),
};

function displayColumn(type, column) {
  return `${column}${REQUIRED_COLUMNS[type].has(column) ? " *" : ""}`;
}

export default function MainCrmUploadsPage() {
  const [uploads, setUploads] = useState([]);
  const [mode, setMode] = useState("CREATE");
  const [type, setType] = useState("INFO_EMAIL_LEADS");
  const [target, setTarget] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    try { setUploads(await getMainCrmUploads()); }
    catch (error) { setMessage(error.message); }
  }

  useEffect(() => { load(); }, []);

  async function submit(event) {
    event.preventDefault();
    if (!file) return setMessage("Choose an Excel or CSV file.");
    if (mode === "UPDATE" && !target) return setMessage("Choose the previous upload to update.");
    try {
      setUploading(true);
      setMessage("");
      const result = await uploadMainCrmLeads(type, file, mode, target);
      setMessage(`${mode === "UPDATE" ? "Updated" : "Created"} upload ${result.unique_number}: ${result.rows_imported} rows imported, ${result.rows_skipped} skipped.`);
      setFile(null);
      event.target.reset();
      await load();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setUploading(false);
    }
  }

  const selectedType = TYPES.find(item => item[0] === type);

  return <div className="page">
    <div className="page-header simple-header"><div><div className="eyebrow">MAIN CRM DATA</div><h1>Excel uploads</h1><p className="page-description">Import lead sources and marketing lifecycle events using normalized email and phone matching.</p></div></div>
    {message && <div className="upload-message page-message">{message}</div>}
    <div className="upload-layout">
      <form className="upload-card" onSubmit={submit}>
        <div className="upload-icon">↑</div><h2>Upload CRM data</h2>
        <label>Action</label>
        <div className="segmented-control"><button type="button" className={mode === "CREATE" ? "segment active" : "segment"} onClick={() => setMode("CREATE")}>New upload</button><button type="button" className={mode === "UPDATE" ? "segment active" : "segment"} onClick={() => setMode("UPDATE")}>Update upload</button></div>
        {mode === "UPDATE" && <><label>Upload to replace</label><select value={target} onChange={event => { setTarget(event.target.value); const item = uploads.find(upload => upload.unique_number === event.target.value); if (item) setType(item.source_category); }}><option value="">Select upload number</option>{uploads.filter(upload => upload.unique_number).map(upload => <option key={upload.id} value={upload.unique_number}>{upload.unique_number} — {upload.filename}</option>)}</select></>}
        <label>Upload type</label>
        <select value={type} onChange={event => setType(event.target.value)}>{TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <p className="small-muted">{selectedType?.[2]}</p>
        <div className="format-item"><strong>This file will receive these columns</strong><p>{COLUMNS[type].map(column => displayColumn(type, column)).join(" | ")}</p><p className="small-muted">* Mandatory column</p></div>
        <label>Excel or CSV file</label>
        <input type="file" accept=".xlsx,.csv" onChange={event => setFile(event.target.files[0] || null)} />
        <button className="primary-button" disabled={uploading}>{uploading ? "Uploading..." : mode === "UPDATE" ? "Replace upload data" : "Create upload"}</button>
      </form>
      <div className="format-card">
        <div className="eyebrow">EXPECTED FORMAT</div><h3>{selectedType?.[1]}</h3>
        <div className="format-item"><strong>All column names</strong>{COLUMNS[type].map((column, index) => <p key={column}>{index + 1}. {displayColumn(type, column)}</p>)}<p className="small-muted">* Mandatory column</p></div>
        <div className="format-item"><strong>Email and phone normalization</strong><p>Email casing and spaces are removed for matching. Phone punctuation and country-code differences are normalized to the final ten digits.</p></div>
        <div className="format-item"><strong>Update upload</strong><p>Select an upload reference to replace its lifecycle rows with the new file.</p></div>
      </div>
    </div>
    <UploadReset onReset={load} />
    <div className="section-heading"><div><div className="eyebrow">UPLOAD REFERENCES</div><h2>Recent Main CRM uploads</h2></div></div>
    <div className="table-card"><table><thead><tr><th>Unique number</th><th>File</th><th>Upload type</th><th>Status</th><th>Rows</th><th>Imported</th><th>Uploaded</th></tr></thead><tbody>{uploads.map(upload => <tr key={upload.id}><td><strong>{upload.unique_number || "Legacy upload"}</strong></td><td>{upload.filename}</td><td>{TYPES.find(source => source[0] === upload.source_category)?.[1] || upload.source_category}</td><td><span className={upload.status === "COMPLETED" ? "status-pill pass" : "status-pill"}>{upload.status}</span></td><td>{upload.rows_total}</td><td>{upload.rows_imported}</td><td>{new Date(upload.uploaded_at).toLocaleString()}</td></tr>)}</tbody></table>{!uploads.length && <div className="table-message">No Main CRM uploads yet.</div>}</div>
  </div>;
}
