import { useEffect, useState } from "react";
import { getLearnersCrmUploads, uploadLearnersCrm } from "../api";
import UploadReset from "../components/UploadReset.jsx";

const COLUMNS = ["enrolment_id", "learner_name", "email_id", "course_name", "enrolment_date", "start_date", "completion_date", "completion_status"];

export default function LearnersCrmUploadsPage() {
  const [uploads, setUploads] = useState([]);
  const [mode, setMode] = useState("CREATE");
  const [target, setTarget] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    try { setUploads(await getLearnersCrmUploads()); }
    catch (error) { setMessage(error.message); }
  }
  useEffect(() => { load(); }, []);

  async function submit(event) {
    event.preventDefault();
    if (!file) return setMessage("Choose an Excel or CSV file.");
    if (mode === "UPDATE" && !target) return setMessage("Choose the learner upload to update.");
    try {
      setUploading(true);
      setMessage("");
      const result = await uploadLearnersCrm(file, mode, target);
      setMessage(`${mode === "UPDATE" ? "Updated" : "Created"} ${result.unique_number}: ${result.rows_imported} enrolments imported, ${result.rows_skipped} skipped.`);
      setFile(null);
      event.target.reset();
      await load();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setUploading(false);
    }
  }

  return <div className="page">
    <div className="page-header simple-header"><div><div className="eyebrow">LEARNERS CRM DATA</div><h1>Learner uploads</h1><p className="page-description">Import learner profiles and course enrolments from Excel.</p></div></div>
    {message && <div className="upload-message page-message">{message}</div>}
    <div className="upload-layout">
      <form className="upload-card" onSubmit={submit}>
        <div className="upload-icon">↑</div><h2>Upload learner data</h2>
        <label>Action</label><div className="segmented-control"><button type="button" className={mode === "CREATE" ? "segment active" : "segment"} onClick={() => setMode("CREATE")}>New upload</button><button type="button" className={mode === "UPDATE" ? "segment active" : "segment"} onClick={() => setMode("UPDATE")}>Update upload</button></div>
        {mode === "UPDATE" && <><label>Upload to replace</label><select value={target} onChange={event => setTarget(event.target.value)} required><option value="">Select upload number</option>{uploads.map(item => <option key={item.id} value={item.unique_number}>{item.unique_number} — {item.filename}</option>)}</select></>}
        <label>Excel or CSV file</label><input type="file" accept=".xlsx,.csv" onChange={event => setFile(event.target.files[0] || null)} />
        <button className="primary-button" disabled={uploading}>{uploading ? "Uploading..." : mode === "UPDATE" ? "Replace learner upload" : "Create learner upload"}</button>
      </form>
      <div className="format-card"><div className="eyebrow">REQUIRED COLUMNS</div><h3>Learner import format</h3>{COLUMNS.map(column => <div className="format-item" key={column}><strong>{column}</strong></div>)}<p className="small-muted">One learner is identified by normalized email. Each course record is identified by enrolment_id.</p></div>
    </div>
    <UploadReset onReset={load} />
    <div className="section-heading"><div><div className="eyebrow">HISTORY</div><h2>Recent learner uploads</h2></div></div>
    <div className="table-card"><table><thead><tr><th>Upload number</th><th>File</th><th>Status</th><th>Rows</th><th>Imported</th><th>Skipped</th><th>Uploaded</th></tr></thead><tbody>{uploads.map(item => <tr key={item.id}><td><strong>{item.unique_number}</strong></td><td>{item.filename}</td><td><span className={item.status === "COMPLETED" ? "status-pill pass" : item.status === "FAILED" ? "status-pill fail" : "status-pill"}>{item.status}</span></td><td>{item.rows_total}</td><td>{item.rows_imported}</td><td>{item.rows_skipped}</td><td>{new Date(item.uploaded_at).toLocaleString()}</td></tr>)}</tbody></table>{!uploads.length && <div className="table-message">No learner uploads yet.</div>}</div>
  </div>;
}
