import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getLearners } from "../api";

export default function LearnersPage() {
  const [learners, setLearners] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(true);
      getLearners(search).then(setLearners).finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);

  return <div className="page">
    <div className="page-header"><div><div className="eyebrow">CRM</div><h1>Learners</h1><p className="page-description">Search learners and inspect their complete learning journey.</p></div></div>
    <div className="toolbar"><input className="search-input" placeholder="Search by learner number, name or email..." value={search} onChange={e => setSearch(e.target.value)} /></div>
    <div className="table-card"><table><thead><tr><th>Learner</th><th>Learner number</th><th>Email</th><th>Phone</th><th>Last activity</th><th></th></tr></thead><tbody>
      {!loading && learners.map(l => <tr key={l.learner_number}><td><div className="learner-cell"><div className="avatar">{l.name?.charAt(0)?.toUpperCase()}</div><strong>{l.name}</strong></div></td><td>{l.learner_number}</td><td>{l.email_id || "—"}</td><td>{l.contact_number || "—"}</td><td>{l.last_activity_date || "—"}</td><td><Link className="text-link" to={`/upsell/learners/${l.learner_number}`}>View →</Link></td></tr>)}
    </tbody></table>{loading && <div className="table-message">Loading learners...</div>}{!loading && learners.length === 0 && <div className="table-message">No learners found.</div>}</div>
  </div>;
}
