export default function UploadProgress({ progress }) {
  if (!progress || progress.status !== "PROCESSING") return null;
  const total = progress.rows_total || 0;
  const processed = progress.processed || 0;
  return <div className="migration-progress" role="status" aria-live="polite">
    <div><strong>{total ? `Processing ${processed.toLocaleString()} of ${total.toLocaleString()} rows` : "Reading and validating file..."}</strong><span>{total ? `${Math.round(processed / total * 100)}%` : ""}</span></div>
    <progress value={processed} max={total || 1} />
    <p className="small-muted">{(progress.rows_imported || 0).toLocaleString()} imported · {(progress.rows_skipped || 0).toLocaleString()} skipped</p>
  </div>;
}
