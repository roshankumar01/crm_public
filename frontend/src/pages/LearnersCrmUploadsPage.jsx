import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getLearnersCrmUploads, startUploadJob } from "../api";
import UploadProgress from "../components/UploadProgress.jsx";
import useUploadJob from "../hooks/useUploadJob.js";

const COLUMNS = ["enrolment_id", "learner_name", "email_id", "phone_number", "course_name", "enrolment_date", "start_date", "completion_date", "completion_status"];

export default function LearnersCrmUploadsPage({ refreshKey = 0 }) {
  const [uploads, setUploads] = useState([]);
  const [mode, setMode] = useState("CREATE");
  const [target, setTarget] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [unmappedCourses, setUnmappedCourses] = useState([]);
  const { begin, jobId, progress } = useUploadJob("learners_crm_upload_job", job => {
    if (job.status === "FAILED") setMessage(`Learner upload failed: ${job.error_message}`);
    else {
      const result = job.result || {};
      setMessage(`Upload complete: ${job.rows_imported} enrolments imported, ${result.rows_mapped || 0} matched to a course category, ${job.rows_skipped} skipped.`);
      setUnmappedCourses(result.unmapped_courses || []);
    }
    load();
  }, error => setMessage(`Could not check upload progress: ${error.message}. Retrying...`));

  async function load() {
    try { setUploads(await getLearnersCrmUploads()); }
    catch (error) { setMessage(error.message); }
  }
  useEffect(() => { load(); }, [refreshKey]);

  async function submit(event) {
    event.preventDefault();
    if (!file) return setMessage("Choose an Excel or CSV file.");
    if (mode === "UPDATE" && !target) return setMessage("Choose the learner upload to update.");
    try {
      setUploading(true);
      setMessage("");
      setUnmappedCourses([]);
      const result = await startUploadJob({ kind: "LEARNERS_CRM", file, uploadMode: mode, uniqueNumber: target });
      begin(result);
      setMessage("Import started. You can leave this page and return to check progress.");
      setFile(null);
      event.target.reset();
      await load();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setUploading(false);
    }
  }

  return <section className="upload-workspace-section">
    {message && <div className="upload-message page-message">{message}</div>}
    <UploadProgress progress={progress} />
    {unmappedCourses.length > 0 && <div className="format-card page-message"><strong>{unmappedCourses.length} course name{unmappedCourses.length === 1 ? " is" : "s are"} unmapped.</strong><p>Assign them to categories in <Link to="/crm/settings/course-mapping">Settings → Course mapping</Link>. Existing enrolments will update automatically.</p><details><summary>Show unmapped course names</summary><ul>{unmappedCourses.map(name => <li key={name}>{name}</li>)}</ul></details></div>}
    <div className="upload-layout">
      <form className="upload-card" onSubmit={submit}>
        <div className="upload-icon">↑</div><h2>Upload learner data</h2>
        <label>Action</label><div className="segmented-control"><button type="button" className={mode === "CREATE" ? "segment active" : "segment"} onClick={() => setMode("CREATE")}>New upload</button><button type="button" className={mode === "UPDATE" ? "segment active" : "segment"} onClick={() => setMode("UPDATE")}>Update upload</button></div>
        {mode === "UPDATE" && <><label>Upload to replace</label><select value={target} onChange={event => setTarget(event.target.value)} required><option value="">Select upload number</option>{uploads.map(item => <option key={item.id} value={item.unique_number}>{item.unique_number} — {item.filename}</option>)}</select></>}
        <label>Excel or CSV file</label><input type="file" accept=".xlsx,.csv" onChange={event => setFile(event.target.files[0] || null)} />
        <button className="primary-button" disabled={uploading || !!jobId || !file}>{uploading ? "Starting import..." : jobId ? "Import in progress" : mode === "UPDATE" ? "Replace learner upload" : "Create learner upload"}</button>
      </form>
      <div className="format-card"><div className="eyebrow">IMPORT COLUMNS</div><h3>Learner import format</h3>{COLUMNS.map(column => <div className="format-item" key={column}><strong>{column}{column === "phone_number" ? " (optional)" : ""}</strong></div>)}<p className="small-muted">Place phone_number after email_id when present. One learner is identified by normalized email. Each course record is identified by enrolment_id.</p></div>
    </div>
    <div className="section-heading"><div><div className="eyebrow">HISTORY</div><h2>Recent learner uploads</h2></div></div>
    <div className="table-card"><table><thead><tr><th>Upload number</th><th>File</th><th>Status</th><th>Rows</th><th>Imported</th><th>Skipped</th><th>Uploaded</th></tr></thead><tbody>{uploads.map(item => <tr key={item.id}><td><strong>{item.unique_number}</strong></td><td>{item.filename}</td><td><span className={item.status === "COMPLETED" ? "status-pill pass" : item.status === "FAILED" ? "status-pill fail" : "status-pill"}>{item.status}</span></td><td>{item.rows_total}</td><td>{item.rows_imported}</td><td>{item.rows_skipped}</td><td>{new Date(item.uploaded_at).toLocaleString()}</td></tr>)}</tbody></table>{!uploads.length && <div className="table-message">No learner uploads yet.</div>}</div>
  </section>;
}
