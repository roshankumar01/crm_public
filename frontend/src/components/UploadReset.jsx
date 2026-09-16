import { useState } from "react";
import { getUploadResetOptions, resetSelectedUploads } from "../api";

const TYPE_LABELS = {
  IGC: "Upsell · IGC",
  IDP: "Upsell · IDP",
  MARKETING_CAMPAIGN: "Upsell · Marketing campaign",
  LEARNERS_CRM: "Learners CRM",
  MAIN_CRM_INFO_EMAIL_LEADS: "Main CRM · Info email leads",
  MAIN_CRM_LIVE_ONLINE_LEADS: "Main CRM · Live online leads",
  MAIN_CRM_DIRECT_CALLS: "Main CRM · Direct calls",
  MAIN_CRM_CAMPAIGN_REPLIES: "Main CRM · Campaign replies",
  MAIN_CRM_CAMPAIGN_DATA: "Main CRM · Campaign data",
};

export default function UploadReset({ onReset }) {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState([]);
  const [selected, setSelected] = useState([]);
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function showOptions() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      setOptions(await getUploadResetOptions());
      setSelected([]);
      setConfirmation("");
      setOpen(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  function close() {
    if (busy) return;
    setOpen(false);
    setSelected([]);
    setConfirmation("");
    setError("");
  }

  function toggle(id) {
    setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
    setConfirmation("");
  }

  async function removeSelected() {
    if (!selected.length || confirmation !== "DELETE SELECTED UPLOADS") return;
    setBusy(true);
    setError("");
    try {
      const result = await resetSelectedUploads(selected);
      setMessage(`${result.uploads_deleted} upload file${result.uploads_deleted === 1 ? "" : "s"} and linked import rows deleted.`);
      setOpen(false);
      setSelected([]);
      setConfirmation("");
      await onReset?.();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="upload-reset-section">
    <div><div className="eyebrow">DATA RESET</div><h2>Delete uploaded data</h2><p>Select the exact uploaded files to remove. Shared people, manual activity, counselor accounts and course definitions are retained.</p></div>
    <button type="button" className="upload-reset-open" onClick={showOptions} disabled={busy}>{busy && !open ? "Loading..." : "Data reset"}</button>
    {message && <div className="upload-message">{message}</div>}
    {!open && error && <div className="upload-message">{error}</div>}
    {open && <div className="upload-reset-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}>
      <div className="upload-reset-dialog" role="dialog" aria-modal="true" aria-labelledby="upload-reset-title">
        <h2 id="upload-reset-title">What uploaded data should be deleted?</h2>
        <p>This permanently deletes the checked upload references and records linked to them. It cannot reconstruct a shared lead’s earlier profile values.</p>
        {options.length ? <>
          <label className="upload-reset-choice"><input type="checkbox" checked={selected.length === options.length} onChange={event => { setSelected(event.target.checked ? options.map(item => item.id) : []); setConfirmation(""); }} /><strong>Select all upload files ({options.length})</strong></label>
          <div className="upload-reset-options">{options.map(item => <label className="upload-reset-choice" key={item.id}>
            <input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} />
            <span><strong>{item.filename}</strong><small>{TYPE_LABELS[item.import_type] || item.import_type} · {item.unique_number || `Upload #${item.id}`} · {item.rows_imported} imported · {new Date(item.uploaded_at).toLocaleString()}</small></span>
          </label>)}</div>
          <p><strong>{selected.length} selected.</strong> Type <code>DELETE SELECTED UPLOADS</code> to confirm.</p>
          <input className="upload-reset-confirmation" value={confirmation} onChange={event => setConfirmation(event.target.value)} placeholder="DELETE SELECTED UPLOADS" aria-label="Type DELETE SELECTED UPLOADS to confirm" />
        </> : <p>No uploaded files are available to reset.</p>}
        {error && <div className="upload-message">{error}</div>}
        <div className="upload-reset-actions"><button type="button" onClick={close} disabled={busy}>Cancel</button><button type="button" className="upload-reset-delete" disabled={busy || !selected.length || confirmation !== "DELETE SELECTED UPLOADS"} onClick={removeSelected}>{busy ? "Deleting..." : `Delete ${selected.length} selected`}</button></div>
      </div>
    </div>}
  </section>;
}
