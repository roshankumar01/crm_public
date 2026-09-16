import { useEffect, useState } from "react";
import { getImportTypes, getUploads, uploadCampaignExcel, uploadExcel } from "../api";
import UploadReset from "../components/UploadReset.jsx";

export default function UploadsPage() {
  const [importTypes, setImportTypes] = useState([]);
  const [importType, setImportType] = useState("");
  const [file, setFile] = useState(null);
  const [campaignFile, setCampaignFile] = useState(null);
  const [uploads, setUploads] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [campaignUploading, setCampaignUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [campaignMessage, setCampaignMessage] = useState("");

  async function loadUploads() {
    setUploads(await getUploads());
  }

  useEffect(() => {
    Promise.all([getImportTypes(), getUploads()]).then(([types, history]) => {
      setImportTypes(types);
      setUploads(history);
      if (types.length) setImportType(types[0].import_type);
    }).catch(e => setMessage(e.message)).finally(() => setLoading(false));
  }, []);

  async function handleUpload(event) {
    event.preventDefault();
    if (!importType || !file) {
      setMessage("Choose an import type and Excel/CSV file.");
      return;
    }
    try {
      setUploading(true);
      setMessage("");
      const result = await uploadExcel(importType, file);
      setMessage(`Imported ${result.rows_imported} course records. ${result.rows_skipped} skipped.`);
      setFile(null);
      event.target.reset();
      await loadUploads();
    } catch (e) {
      setMessage(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleCampaignUpload(event) {
    event.preventDefault();
    if (!campaignFile) {
      setCampaignMessage("Choose a campaign Excel/CSV file.");
      return;
    }
    try {
      setCampaignUploading(true);
      setCampaignMessage("");
      const result = await uploadCampaignExcel(campaignFile);
      const created = result.learners_created ? ` Created ${result.learners_created} new learner records.` : "";
      const duplicates = result.duplicates_skipped ? ` ${result.duplicates_skipped} duplicate rows were not imported again.` : "";
      setCampaignMessage(`Imported ${result.rows_imported} campaign rows.${created}${duplicates}`);
      setCampaignFile(null);
      event.target.reset();
      await loadUploads();
    } catch (e) {
      setCampaignMessage(e.message);
    } finally {
      setCampaignUploading(false);
    }
  }

  if (loading) return <div className="page">Loading upload system...</div>;
  const selectedImporter = importTypes.find(item => item.import_type === importType);
  const displayColumn = column => `${column.name}${column.required ? " *" : ""}`;

  return <div className="page">
    <div className="page-header"><div><div className="eyebrow">DATA MANAGEMENT</div><h1>Excel uploads</h1><p className="page-description">Admin-only course imports and learner marketing-campaign imports.</p></div></div>

    <div className="upload-layout">
      <form className="upload-card" onSubmit={handleUpload}>
        <div className="upload-icon">↑</div><h2>Upload course data</h2><p>Choose the course importer and upload its Excel or CSV file. These rows create learning-history records.</p>
        <label>Import type</label><select value={importType} onChange={e => setImportType(e.target.value)}>{importTypes.map(t => <option key={t.import_type} value={t.import_type}>{t.display_name}</option>)}</select>
        {selectedImporter && <div className="format-item"><strong>This file will receive these columns</strong><p>{selectedImporter.columns.map(displayColumn).join(" | ")}</p><p className="small-muted">* Mandatory column</p></div>}
        <label>File</label><input type="file" accept=".xlsx,.csv" onChange={e => setFile(e.target.files[0] || null)} />
        <button type="submit" className="primary-button" disabled={uploading}>{uploading ? "Uploading..." : "Upload course file"}</button>
        {message && <div className="upload-message">{message}</div>}
      </form>
      <div className="format-card"><div className="eyebrow">EXPECTED FORMAT</div><h3>{selectedImporter?.display_name || "Course importer"}</h3><p>{selectedImporter?.description}</p><div className="format-item"><strong>All accepted column names</strong>{selectedImporter?.columns.map((column, index) => <div key={column.name}><p>{index + 1}. {displayColumn(column)}</p>{column.note && <p className="small-muted">{column.note}</p>}</div>)}<p className="small-muted">* Mandatory column. IDP also requires either a course-style column or at least one ID result column.</p></div></div>
    </div>

    <div className="upload-layout campaign-upload-section">
      <form className="upload-card" onSubmit={handleCampaignUpload}>
        <div className="upload-icon">M</div><h2>Upload marketing campaigns</h2><p>Campaigns are linked by learner number. If a learner is new, a basic learner profile is created automatically and can be completed later.</p>
        <div className="format-item"><strong>This file will receive these columns</strong><p>Learner number * | Marketing type * | Campaign name *</p><p className="small-muted">* Mandatory column</p></div>
        <label>Campaign file</label><input type="file" accept=".xlsx,.csv" onChange={e => setCampaignFile(e.target.files[0] || null)} />
        <button type="submit" className="primary-button" disabled={campaignUploading}>{campaignUploading ? "Uploading..." : "Upload campaign file"}</button>
        {campaignMessage && <div className="upload-message">{campaignMessage}</div>}
      </form>
      <div className="format-card"><div className="eyebrow">REQUIRED COLUMNS</div><h3>Marketing campaign format</h3><div className="format-item"><strong>Learner number *</strong><p>Must match an existing learner, or a basic learner profile will be created.</p></div><div className="format-item"><strong>Marketing type *</strong><p>For example: Email, WhatsApp, SMS or Event.</p></div><div className="format-item"><strong>Campaign name *</strong><p>The name used to identify the campaign.</p></div><p className="small-muted">* Mandatory column</p></div>
    </div>

    <UploadReset onReset={loadUploads} />
    <div className="section-heading"><div><div className="eyebrow">HISTORY</div><h2>Recent uploads</h2></div></div>
    <div className="table-card"><table><thead><tr><th>File</th><th>Type</th><th>Status</th><th>Rows</th><th>Imported</th><th>Skipped</th><th>Uploaded</th></tr></thead><tbody>{uploads.map(u => <tr key={u.id}><td>{u.filename}</td><td>{u.import_type}</td><td><span className={u.status === "COMPLETED" ? "status-pill pass" : u.status === "FAILED" ? "status-pill fail" : "status-pill"}>{u.status}</span></td><td>{u.rows_total}</td><td>{u.rows_imported}</td><td>{u.rows_skipped}</td><td>{new Date(u.uploaded_at).toLocaleString()}</td></tr>)}</tbody></table>{uploads.length === 0 && <div className="table-message">No uploads yet.</div>}</div>
  </div>;
}
