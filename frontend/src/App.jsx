import { useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  CircleDashed,
  FileText,
  LockKeyhole,
  LoaderCircle,
  Moon,
  Play,
  ShieldCheck,
  Sun,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import zavaColorLogo from "../logos/zava-securities-color-logo.svg";
import zavaWhiteLogo from "../logos/zava-securities-white-logo.svg";
import { startRun, submitApproval } from "./api/stream.js";

const QUESTION =
  "Gulf Lantern Fictional ISD is issuing about $85 million of unlimited tax school " +
  "building bonds this fall. Pull the most comparable Texas ISD issues from the last " +
  "18 months, compare debt service and call features, flag evidence gaps, and draft " +
  "the market summary section for our RFP response.";

const STAGES = [
  ["plan-request", "Plan request"],
  ["research-public-comparables", "Research comparables"],
  ["compute-subject-debt-service", "Compute debt service"],
  ["assess-comparables", "Assess structures"],
  ["synthesize-draft", "Draft market summary"],
  ["review-draft", "Apply compliance controls"],
];

const STAGE_STATUS = {
  "plan-request": "Orchestrator is asking the model router to plan specialist work.",
  "research-public-comparables": "Orchestrator is delegating cited retrieval to Research.",
  "compute-subject-debt-service": "Orchestrator is invoking the deterministic calculator.",
  "assess-comparables": "Orchestrator is handing Research evidence to the Analyst agent.",
  "synthesize-draft": "Orchestrator is joining specialist handoffs for synthesis.",
  "review-draft": "Orchestrator is delegating review to Compliance and policy tools.",
};

function Markdown({ children }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

function IdentitySwitcher({ value, disabled, onChange }) {
  return (
    <div className="identity-switch" role="group" aria-label="Demo identity">
      <button
        className={value === "public_side" ? "selected" : ""}
        disabled={disabled}
        onClick={() => onChange("public_side")}
      >
        <UserRound size={16} /> Public-side analyst
      </button>
      <button
        className={value === "deal_team" ? "selected" : ""}
        disabled={disabled}
        onClick={() => onChange("deal_team")}
      >
        <UsersRound size={16} /> Deal-team member
      </button>
    </div>
  );
}

function ThemeToggle({ theme, onToggle }) {
  const dark = theme === "dark";
  return (
    <button
      className="theme-toggle"
      onClick={onToggle}
      title={`Use ${dark ? "light" : "dark"} theme`}
      aria-label={`Use ${dark ? "light" : "dark"} theme`}
    >
      {dark ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  );
}

function StageTimeline({ stages, running }) {
  return (
    <section className="rail-section" aria-label="Workflow progress">
      <h2>Workflow</h2>
      <ol className="timeline">
        {STAGES.map(([key, label]) => {
          const status = stages[key] || "pending";
          return (
            <li key={key} data-status={status}>
              <span className="stage-icon">
                {status === "completed" ? (
                  <Check size={14} />
                ) : status === "started" ? (
                  <LoaderCircle className="spinner" size={15} />
                ) : (
                  <CircleDashed size={14} />
                )}
              </span>
              <span>{label}</span>
            </li>
          );
        })}
      </ol>
      {running && <div className="live-indicator">Live</div>}
    </section>
  );
}

function EvidenceTable({ answer, streamedSources }) {
  const sources = streamedSources.length ? streamedSources : answer?.evidence_sources || [];
  return (
    <details className="panel evidence-panel">
      <summary className="panel-heading">
        <div>
          <span className="eyebrow">Evidence</span>
          <h2>Sources considered</h2>
        </div>
        <div className="evidence-summary-meta">
          <span className="source-count">{sources.length} sources</span>
          {answer?.partial_due_to_permissions && (
            <span className="withheld"><LockKeyhole size={14} /> Results withheld</span>
          )}
          <ChevronDown className="disclosure-icon" size={18} />
        </div>
      </summary>
      {sources.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Source</th><th>Deal</th><th>Type</th><th>Access</th></tr></thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.document_id}>
                  <td>{source.document_title}</td>
                  <td>{source.deal_id}</td>
                  <td>{source.source_type.replaceAll("_", " ")}</td>
                  <td><span className={`sensitivity ${source.sensitivity}`}>{source.sensitivity}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="empty">Evidence appears when the workflow reaches retrieval.</p>}
    </details>
  );
}

function PolicyPanel({ policies }) {
  return (
    <section className="rail-section">
      <h2>Controls</h2>
      <div className="policy-list">
        {policies.length ? policies.map((finding) => (
          <div className="policy" key={`${finding.policy_id}-${finding.passed}`}>
            {finding.passed ? <ShieldCheck size={16} /> : <AlertTriangle size={16} />}
            <div><strong>{finding.policy_id}</strong><p>{finding.detail}</p></div>
          </div>
        )) : <p className="empty">Policy findings appear after review.</p>}
      </div>
    </section>
  );
}

function DraftView({ answer, outcome }) {
  if (!answer) {
    return (
      <section className="panel draft-panel empty-draft">
        <FileText size={28} />
        <h2>Market summary</h2>
        <p>The held draft will assemble here after analysis.</p>
      </section>
    );
  }
  const blocked = outcome === "blocked" || answer.compliance?.blocking;
  const approved = outcome === "approved";
  return (
    <section className={`panel draft-panel ${blocked ? "blocked" : ""}`}>
      <div className="panel-heading">
        <div><span className="eyebrow">Draft</span><h2>Market summary</h2></div>
        <span className={blocked ? "status danger" : "status success"}>
          {blocked ? <X size={14} /> : <Check size={14} />}
          {blocked ? "Blocked" : approved ? "Approved" : "Review required"}
        </span>
      </div>
      <div className="summary"><Markdown>{answer.summary}</Markdown></div>
      {answer.sections.map((section) => (
        <article key={section.heading}>
          <h3>{section.heading}</h3>
          <Markdown>{section.body}</Markdown>
          <div className="citation-row">
            {section.citations.map((citation) => (
              <span title={citation.excerpt} key={`${section.heading}-${citation.document_id}`}>
                {citation.document_title}
              </span>
            ))}
          </div>
        </article>
      ))}
      <dl className="metrics">
        <div><dt>Comparables</dt><dd>{answer.comparables_considered}</dd></div>
        <div><dt>Total debt service</dt><dd>{answer.total_debt_service ? `$${Number(answer.total_debt_service).toLocaleString()}` : "—"}</dd></div>
        <div><dt>Evidence gaps</dt><dd>{answer.gaps.length}</dd></div>
      </dl>
    </section>
  );
}

export default function App() {
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute("data-theme") || "light",
  );
  const [identity, setIdentity] = useState("deal_team");
  const [question, setQuestion] = useState(QUESTION);
  const [stages, setStages] = useState({});
  const [citations, setCitations] = useState([]);
  const [evidenceSources, setEvidenceSources] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [answer, setAnswer] = useState(null);
  const [outcome, setOutcome] = useState(null);
  const [approval, setApproval] = useState(null);
  const [runId, setRunId] = useState(null);
  const [running, setRunning] = useState(false);
  const [liveStatus, setLiveStatus] = useState("");
  const [stageStatuses, setStageStatuses] = useState({});
  const [error, setError] = useState(null);

  function handleEvent(name, payload) {
    if (name === "stage") {
      setStages((current) => ({ ...current, [payload.stage]: payload.status }));
      if (payload.status === "started") {
        setStageStatuses((current) => ({
          ...current,
          [payload.stage]: current[payload.stage]
            || STAGE_STATUS[payload.stage]
            || "Continuing workflow analysis.",
        }));
      }
    }
    if (name === "status") {
      if (payload.stage) {
        setStageStatuses((current) => ({ ...current, [payload.stage]: payload.message }));
      } else {
        setLiveStatus(payload.message);
      }
    }
    if (name === "citation") {
      setCitations((current) => current.some((item) => item.document_id === payload.citation.document_id) ? current : [...current, payload.citation]);
    }
    if (name === "evidence") {
      setEvidenceSources((current) => current.some((item) => item.document_id === payload.evidence_source.document_id) ? current : [...current, payload.evidence_source]);
    }
    if (name === "draft") {
      setAnswer((current) => ({
        ...(current || {}),
        ...payload.draft,
        evidence_sources: evidenceSources,
        comparables_considered: current?.comparables_considered || 0,
        total_debt_service: current?.total_debt_service || null,
        compliance: current?.compliance || null,
        partial_due_to_permissions: current?.partial_due_to_permissions || false,
        requires_human_review: true,
      }));
    }
    if (name === "policy") {
      setPolicies((current) => current.some((item) => item.policy_id === payload.finding.policy_id) ? current : [...current, payload.finding]);
    }
    if (name === "approval_required") {
      setApproval(payload);
      setAnswer(payload.request.draft);
      setLiveStatus("Analysis complete. Waiting for supervising-principal review.");
    }
    if (name === "final") {
      setOutcome(payload.outcome);
      setAnswer(payload.answer);
      setApproval(null);
      setLiveStatus(payload.outcome === "approved" ? "Review approved." : "Workflow complete.");
    }
    if (name === "error") {
      setError(payload.message);
      setLiveStatus("Workflow stopped before completion.");
    }
  }

  async function submit() {
    setStages({}); setCitations([]); setEvidenceSources([]); setPolicies([]); setAnswer(null);
    setOutcome(null); setApproval(null); setError(null); setStageStatuses({});
    setLiveStatus("Starting workflow."); setRunning(true);
    try {
      const id = await startRun({ question, identity }, handleEvent);
      setRunId(id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRunning(false);
    }
  }

  async function decide(approved) {
    setRunning(true); setError(null); setLiveStatus("Submitting supervising-principal decision.");
    try {
      await submitApproval(runId, { approved, reviewer_notes: approved ? "Reviewed in front door." : "Rejected in front door." }, handleEvent);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRunning(false);
    }
  }

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", nextTheme);
    setTheme(nextTheme);
  }

  const activeStatuses = STAGES
    .filter(([stage]) => stages[stage] === "started")
    .map(([stage]) => stageStatuses[stage] || STAGE_STATUS[stage])
    .filter(Boolean);
  const displayedStatus = activeStatuses.length > 1
    ? `Parallel work: ${activeStatuses.join(" • ")}`
    : activeStatuses[0] || liveStatus;

  return (
    <div className="app-shell">
      <header>
        <div className="brand">
          <img className="brand-logo brand-logo-light" src={zavaColorLogo} alt="Zava Securities" />
          <img className="brand-logo brand-logo-dark" src={zavaWhiteLogo} alt="Zava Securities" />
          <div className="product-name"><strong>Municipal Deal Desk</strong><small>Synthetic public finance demonstration</small></div>
        </div>
        <div className="header-actions">
          <IdentitySwitcher value={identity} disabled={running || Boolean(approval)} onChange={setIdentity} />
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
      </header>
      <main>
        <aside>
          <StageTimeline stages={stages} running={running} />
          <PolicyPanel policies={policies} />
        </aside>
        <div className="workspace">
          <section className="query-band">
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} disabled={running || Boolean(approval)} aria-label="Deal Desk question" />
            <div className="query-actions">
              <div className="workflow-status" aria-live="polite" aria-atomic="true">
                {running && <LoaderCircle className="spinner" size={16} />}
                <span>{displayedStatus}</span>
              </div>
              <button className="run-button" onClick={submit} disabled={running || Boolean(approval) || question.trim().length < 10} title="Run analysis">
                {running ? <LoaderCircle className="spinner" size={17} /> : <Play size={17} />}
                {running ? "Running" : "Run analysis"}
              </button>
            </div>
          </section>
          {error && <div className="error-banner"><AlertTriangle size={16} />{error}</div>}
          <EvidenceTable answer={answer} streamedSources={evidenceSources} />
          <DraftView answer={answer} outcome={outcome} />
        </div>
        <aside className="citations-rail">
          <section className="rail-section">
            <h2>Citations</h2>
            <div className="source-list">
              {citations.length ? citations.map((citation, index) => (
                <button key={`${citation.document_id}-${index}`} title={citation.excerpt}>
                  <FileText size={15} /><span>{citation.document_title}</span>
                </button>
              )) : <p className="empty">Resolved passages appear during synthesis.</p>}
            </div>
          </section>
        </aside>
      </main>
      {approval && (
        <div className="approval-bar">
          <div><ShieldCheck size={20} /><span><strong>Supervising-principal review</strong><small>{approval.request.instruction}</small></span></div>
          <div className="approval-actions">
            <button className="reject" onClick={() => decide(false)} disabled={running}><X size={16} /> Reject</button>
            <button className="approve" onClick={() => decide(true)} disabled={running}><Check size={16} /> Approve</button>
          </div>
        </div>
      )}
    </div>
  );
}