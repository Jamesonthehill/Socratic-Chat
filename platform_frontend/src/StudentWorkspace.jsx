import SocraticLearningSummary from "./SocraticLearningSummary";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Markdown from "react-markdown";
import { api, date, session, TOOLS } from "./api";
import { Badge, GenerationStatus, Notice } from "./ui";

function nextQuestion(messages) {
  const answer = [...(messages || [])]
    .reverse()
    .find((item) => item.role === "assistant")?.content;
  if (!answer) return "";
  const sentences = answer.split(/(?<=[.!?])\s+/).filter(Boolean);
  return (
    [...sentences]
      .reverse()
      .find((sentence) => sentence.trim().endsWith("?")) || answer
  ).trim();
}

function moneyBreakdownFromQuestion(text) {
  if (!text || !/\b(?:insert|pay|paid|coin|cash|change|costs?)\b/i.test(text)) return null;
  const priceMatch = text.match(/\b(?:costs?|price(?: is| of)?)\s*(?:\$|USD\s*)(\d+(?:\.\d{1,2})?)\b/i);
  if (!priceMatch) return null;
  const numberWords = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10 };
  const denominations = [
    { pattern: "large dollars?", label: "Large dollar", value: "$1.00" },
    { pattern: "half dollars?", label: "Half dollar", value: "$0.50" },
    { pattern: "quarters?", label: "Quarter", value: "$0.25" },
    { pattern: "dimes?", label: "Dime", value: "$0.10" },
    { pattern: "nickels?", label: "Nickel", value: "$0.05" },
    { pattern: "penn(?:y|ies)", label: "Penny", value: "$0.01" },
    { pattern: "dollars?", label: "Dollar", value: "$1.00" },
  ];
  const rows = [];
  for (const denomination of denominations) {
    const countMatch = text.match(new RegExp(`\\b(\\d+|one|two|three|four|five|six|seven|eight|nine|ten)\\s+${denomination.pattern}\\b`, "i"));
    if (countMatch) {
      rows.push({
        label: denomination.label,
        count: numberWords[countMatch[1].toLowerCase()] || Number(countMatch[1]),
        value: denomination.value,
      });
    }
  }
  return rows.length ? { rows, price: `$${Number(priceMatch[1]).toFixed(2)}` } : null;
}

function structuredEvidence(text) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return [];
  const fragments = normalized.split(/(?<=[.!?])\s+(?=[A-Z]|how\b|what\b|if\b|when\b)/i);
  return fragments.filter((fragment) => fragment.length >= 12).map((fragment) => {
    const excerpt = fragment.trim();
    let kind = "Source detail";
    if (/\b(?:sorry|refund(?:ed)?|ready|change|display|output|result)\b/i.test(excerpt)) {
      kind = "Outcome";
    } else if (/\b(?:insert|enter|choose|select|input|prompt)\b|\?/i.test(excerpt)) {
      kind = "Input or choice";
    } else if (/\b(?:check|must|require|enough|available|if|when)\b/i.test(excerpt)) {
      kind = "Rule or check";
    }
    return { kind, excerpt };
  });
}

function transcriptEvidence(text) {
  const source = String(text || "").replace(/\s+/g, " ").trim();
  const prompt = /What would you like\?\s*\([^)]*\)\s*:\s*([^\s]+)/gi;
  const matches = [...source.matchAll(prompt)];
  if (matches.length < 2) return null;
  const rows = matches.map((match, index) => {
    const segment = source.slice(match.index + match[0].length, matches[index + 1]?.index ?? source.length);
    const coins = [...segment.matchAll(/how many\s+([^?:]{2,35})\?\s*:\s*(\d+)/gi)]
      .map((entry) => `${entry[1].trim()}: ${entry[2]}`);
    const outcome = segment
      .replace(/Please insert coins\.?/gi, "")
      .replace(/how many\s+[^?:]{2,35}\?\s*:\s*\d+/gi, "")
      .trim();
    return { choice: match[1], coins, outcome: outcome || "—" };
  });
  return { initial: source.slice(0, matches[0].index).trim(), rows };
}

function EmphasizedText({ text, keywords = [] }) {
  const terms = keywords
    .map((keyword) => keyword.trim())
    .filter(Boolean)
    .sort((left, right) => right.length - left.length);
  if (!terms.length) return text;
  const escaped = terms.map((term) =>
    term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
  );
  const matcher = new RegExp(`(${escaped.join("|")})`, "gi");
  return text
    .split(matcher)
    .map((part, index) =>
      terms.some((term) => term.toLowerCase() === part.toLowerCase()) ? (
        <strong key={index}>{part}</strong>
      ) : (
        part
      ),
    );
}

function messageTime(createdAt) {
  const parsed = createdAt ? new Date(createdAt) : new Date();
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(Number.isNaN(parsed.getTime()) ? new Date() : parsed);
}

function maximumEvidenceWidth() {
  const workspaceWidth = window.innerWidth - 48;
  return Math.max(320, workspaceWidth - 444);
}

function SocraticThinkingMessage({ elapsedSeconds }) {
  return (
    <GenerationStatus
      title="Socratic tutor"
      message="Thinking through your response"
      elapsedSeconds={elapsedSeconds}
      ariaLabel="Socratic tutor is thinking through your response"
      messageCard
    />
  );
}

function ConceptCheck({
  check,
  selectedOption,
  busy,
  hintVisible,
  onShowHint,
  onSelect,
}) {
  return (
    <section className="concept-check">
      <div className="concept-check-heading">
        <p className="context">Quick concept check</p>
        <button
          type="button"
          className="secondary compact"
          aria-expanded={hintVisible}
          onClick={onShowHint}
        >
          {hintVisible ? "Hide hint" : "Show hint"}
        </button>
      </div>
      {hintVisible && (
        <p className="concept-check-hint" role="note">
          <strong>Hint:</strong> {check.hint}
        </p>
      )}
      <fieldset disabled={busy}>
        <legend>{check.question}</legend>
        <div className="concept-check-options">
          {check.options.map((option, index) => (
            <label
              className={`concept-check-option${
                selectedOption === index ? " is-selected" : ""
              }`}
              key={option.id}
            >
              <input
                type="radio"
                name="concept-check-option"
                value={index}
                checked={selectedOption === index}
                onChange={() => onSelect(index)}
              />
              <span>{option.text}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {busy && <p className="help" role="status">Checking your answer…</p>}
    </section>
  );
}

function EvidenceDrawer({
  assignmentId,
  evidence,
  keywords,
  width,
  onClose,
  onResizeStart,
  onResize,
  onResizeEnd,
  onResizeKeyDown,
}) {
  const [diagram, setDiagram] = useState(null);
  const [diagramBusy, setDiagramBusy] = useState(false);
  const [diagramError, setDiagramError] = useState("");
  const [showOriginal, setShowOriginal] = useState(false);
  useEffect(() => {
    setDiagram(null);
    setDiagramBusy(false);
    setDiagramError("");
    setShowOriginal(false);
  }, [evidence?.chunk_id]);
  async function createDiagram() {
    if (!assignmentId || !evidence?.chunk_id) return;
    setDiagramBusy(true);
    setDiagramError("");
    try {
      const result = await api(`/platform/assignments/${assignmentId}/evidence-diagram`, {
        method: "POST", body: { chunk_id: evidence.chunk_id },
      });
      if (!result.steps?.length) {
        setDiagramError("This passage does not have a clear sequence to diagram. You can open the original text below.");
      } else {
        setDiagram(result.steps);
        setShowOriginal(false);
      }
    } catch (error) {
      setDiagramError(error.message);
    } finally {
      setDiagramBusy(false);
    }
  }
  useEffect(() => {
    if (!evidence) return;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      document.body.classList.remove("is-resizing-evidence");
    };
  }, [evidence, onClose]);

  if (!evidence) return null;
  const details = structuredEvidence(evidence.text);
  const transcript = transcriptEvidence(evidence.text);
  return (
    <aside
      className="evidence-drawer"
      id="evidence-document-drawer"
      role="dialog"
      aria-label={`Evidence document: ${evidence.title}`}
      style={{ "--evidence-drawer-width": `${width}px` }}
    >
      <div
        className="evidence-drawer-resizer"
        role="separator"
        aria-label="Resize evidence document"
        aria-orientation="vertical"
        aria-valuemin={320}
        aria-valuemax={maximumEvidenceWidth()}
        aria-valuenow={Math.round(width)}
        tabIndex={0}
        onPointerDown={onResizeStart}
        onPointerMove={onResize}
        onPointerUp={onResizeEnd}
        onPointerCancel={onResizeEnd}
        onKeyDown={onResizeKeyDown}
      />
      <header className="evidence-drawer-header">
        <div>
          <span>Evidence document</span>
          <h2>{evidence.title}</h2>
        </div>
        <button
          type="button"
          className="quiet evidence-drawer-close"
          aria-label="Close evidence document"
          onClick={onClose}
          autoFocus
        >
          ×
        </button>
      </header>
      <div className="evidence-drawer-meta">
        {evidence.page_number && <span>Page {evidence.page_number}</span>}
        {evidence.chunk_id && <span>Passage {evidence.chunk_id}</span>}
        <span>Published assignment snapshot</span>
      </div>
      <div className="evidence-diagram-actions">
        <button type="button" className="secondary compact" onClick={createDiagram} disabled={diagramBusy}>
          {diagramBusy ? "Making visual steps…" : diagram ? "Regenerate visual steps" : "Make visual steps"}
        </button>
        <button type="button" className="quiet compact" aria-expanded={showOriginal} onClick={() => setShowOriginal((value) => !value)}>
          {showOriginal ? "Hide original text" : "Show original text"}
        </button>
      </div>
      {diagramError && <p className="help" role="status">{diagramError}</p>}
      {!diagram && <section className="evidence-structured" aria-label="Structured source evidence">
        <h3>Evidence at a glance</h3>
        <p className="help">These are exact details from the selected passage, organized for reading—not a generated answer.</p>
        {transcript ? <>
          {transcript.initial && <p className="evidence-initial-stock"><strong>Before the first choice:</strong> {transcript.initial}</p>}
          <div className="evidence-transcript-table"><table>
            <thead><tr><th scope="col">Turn</th><th scope="col">Choice</th><th scope="col">Coins entered</th><th scope="col">Recorded outcome</th></tr></thead>
            <tbody>{transcript.rows.map((row, index) => <tr key={index}>
              <th scope="row">{index + 1}</th><td>{row.choice}</td><td>{row.coins.length ? row.coins.join(" · ") : "—"}</td><td>{row.outcome}</td>
            </tr>)}</tbody>
          </table></div>
        </> : details.length ? <ol>{details.slice(0, 12).map((detail, index) => <li key={`${index}-${detail.excerpt}`}>
          <span>{detail.kind}</span><p>{detail.excerpt}</p>
        </li>)}</ol> : <p className="help">No readable details were extracted from this passage.</p>}
        {!transcript && details.length > 12 && <p className="help">Showing 12 of {details.length} details. Open the original text to see the whole passage.</p>}
      </section>}
      {diagram && <section className="evidence-flow" aria-label="Visual steps from this passage">
        <h3>Passage flow</h3>
        <p className="help">Each step is quoted from this passage, in source order.</p>
        <ol>{diagram.map((step, index) => <li key={`${index}-${step}`}><span>Step {index + 1}</span><p>{step}</p></li>)}</ol>
      </section>}
      {showOriginal && <article className="evidence-drawer-passage">
        <span>Original selected passage</span>
        <p><EmphasizedText text={evidence.text} keywords={keywords} /></p>
      </article>}
      <p className="evidence-drawer-note">
        This passage comes from the frozen document version attached when the
        assignment was published.
      </p>
    </aside>
  );
}

function SocraticMessage({
  message,
  studentName,
  isPending = false,
  latest,
  thinkingStep,
  keywords,
  sources,
  responseSeconds,
  selectedEvidence,
  setSelectedEvidence,
}) {
  const [showSources, setShowSources] = useState(false);
  const visualCue = latest && message.role === "assistant"
    ? message.content.match(/\b(table|equation|formula|figure|chart|graph|matrix)\b/i)?.[1]
    : null;
  const visualSource = visualCue && sources?.find((source) => {
    const content = source.text || "";
    return new RegExp(`\\b${visualCue}\\b`, "i").test(content) ||
      (["equation", "formula"].includes(visualCue.toLowerCase()) && /[=∑∫]/.test(content));
  });
  const visualText = visualSource?.text || "";
  const visualStart = Math.max(0, visualText.search(/\b(?:table|equation|formula|figure|chart|graph|matrix)\b|[=∑∫]/i) - 100);
  const visualExcerpt = visualText.slice(visualStart, visualStart + 650).trim();
  const moneyBreakdown = message.role === "assistant"
    ? moneyBreakdownFromQuestion(message.content) || (latest ? moneyBreakdownFromQuestion(thinkingStep) : null)
    : null;
  const question =
    message.role === "assistant"
      ? latest
        ? thinkingStep
        : nextQuestion([message])
      : "";
  const showQuestion =
    question.endsWith("?") && message.content.trim().endsWith(question);
  const lead =
    showQuestion
      ? message.content.trim().slice(0, -question.length).trim()
      : message.content;
  return (
    <article
      className={`message socratic-message-card ${message.role}${isPending ? " is-pending" : ""}`}
    >
      <header className="message-card-header">
        <div className="message-card-identity">
          <span className="message-avatar" aria-hidden="true">
            {message.role === "user"
              ? studentName.charAt(0).toUpperCase()
              : "S"}
          </span>
          <strong>
            {message.role === "user" ? studentName : "Socratic tutor"}
          </strong>
        </div>
        <div className="message-card-meta">
          {isPending && <span>Sending…</span>}
          <time>{messageTime(message.created_at)}</time>
          {latest && responseSeconds !== null && (
            <span>Generated in {Math.max(1, Math.round(responseSeconds))}s</span>
          )}
        </div>
      </header>
      <div className="message-card-body">
        {message.role === "assistant" && showQuestion ? (
          <>
            {lead && (
              <div className="prose message-lead">
                <Markdown>{lead}</Markdown>
              </div>
            )}
            <section
              className="message-thinking-step"
              aria-label="Your next thinking step"
            >
              <span>Your next thinking step</span>
              <p>
                <EmphasizedText text={question} keywords={keywords} />
              </p>
            </section>
          </>
        ) : (
          <div className="prose">
            <Markdown>{message.content}</Markdown>
          </div>
        )}
      </div>
      {moneyBreakdown && <section className="message-calculation-aid" aria-label="Money breakdown">
        <strong>Organize the amounts</strong>
        <p>Use the counts from the question to work out each amount, then compare the total with the sandwich price.</p>
        <table>
          <thead><tr><th scope="col">Coin</th><th scope="col">Count</th><th scope="col">Each</th><th scope="col">Amount</th></tr></thead>
          <tbody>{moneyBreakdown.rows.map((row) => <tr key={row.label}>
            <th scope="row">{row.label}</th><td>{row.count}</td><td>{row.value}</td><td>?</td>
          </tr>)}</tbody>
          <tfoot><tr><th scope="row" colSpan="3">Total inserted</th><td>?</td></tr>
            <tr><th scope="row" colSpan="3">Sandwich price</th><td>{moneyBreakdown.price}</td></tr>
            <tr><th scope="row" colSpan="3">Change</th><td>?</td></tr></tfoot>
        </table>
      </section>}
      {latest && sources?.length > 0 && (
        <div className="message-evidence">
          {visualSource && <section className="message-visual-reference" aria-label="Relevant source excerpt">
            <strong>Relevant {visualCue.toLowerCase()} from your course material</strong>
            <p className="help">Text extracted from {visualSource.title}{visualSource.page_number ? `, page ${visualSource.page_number}` : ""}.</p>
            <pre>{visualExcerpt}</pre>
          </section>}
          <button type="button" className="quiet compact" aria-expanded={showSources} onClick={() => setShowSources((current) => !current)}>
            {showSources ? "Hide supporting sources" : "View supporting sources"}
          </button>
          {showSources && <div>
            {sources.map((source, index) => (
              <button
                type="button"
                className="evidence-chip"
                key={source.chunk_id || index}
                aria-pressed={selectedEvidence?.chunk_id === source.chunk_id}
                aria-controls="evidence-document-drawer"
                aria-expanded={selectedEvidence?.chunk_id === source.chunk_id}
                onClick={() =>
                  setSelectedEvidence((current) =>
                    current?.chunk_id === source.chunk_id ? null : source,
                  )
                }
              >
                {source.title}
                {source.page_number ? ` · page ${source.page_number}` : ""}
              </button>
            ))}
          </div>}
        </div>
      )}
    </article>
  );
}

function Result({ result }) {
  if (!result) return null;
  const evaluation = result.evaluation;
  return (
    <section className="result">
      <h2 className="result-complete-title">Assignment complete</h2>
      <p>Your work has been saved and your professor can see your progress.</p>
      {evaluation && (
        <>
          <div className="result-stats">
            <span>
              Reflection depth{" "}
              <strong>{evaluation.reflection_depth_score}</strong>
            </span>
            <span>
              Confidence <strong>{evaluation.confidence_level}</strong>
            </span>
            <span>
              Engagement <strong>{evaluation.engagement_score}</strong>
            </span>
          </div>
          {[
            ["Topics covered", evaluation.topics_covered],
            ["Topics to revisit", evaluation.missing_topics],
            ["Misconceptions to review", evaluation.misconceptions],
          ].map(([title, items]) =>
            items?.length ? (
              <div key={title}>
                <h3>{title}</h3>
                <ul>
                  {items.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
        </>
      )}
      {result.similar?.length > 0 && (
        <>
          <h3>Related experiences</h3>
          {result.similar.map((item, i) => (
            <article className="related" key={i}>
              <p>
                <strong>Challenge:</strong> {item.challenge}
              </p>
              <p>
                <strong>Solution:</strong> {item.solution}
              </p>
            </article>
          ))}
        </>
      )}
    </section>
  );
}

export default function StudentWorkspace({ user }) {
  const studentName = user?.display_name?.trim() || user?.username || "Student";
  const { id } = useParams();
  const [assignment, setAssignment] = useState(null),
    [attempt, setAttempt] = useState(null),
    [message, setMessage] = useState(""),
    [studentReflection, setStudentReflection] = useState("");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [outgoingMessage, setOutgoingMessage] = useState(null),
    [loaded, setLoaded] = useState(false),
    [generationStartedAt, setGenerationStartedAt] = useState(null),
    [generationSeconds, setGenerationSeconds] = useState(0),
    [lastGenerationSeconds, setLastGenerationSeconds] = useState(null),
    [finalFeedbackBusy, setFinalFeedbackBusy] = useState(false),
    [selectedEvidence, setSelectedEvidence] = useState(null),
    [materials, setMaterials] = useState([]),
    [materialsLoading, setMaterialsLoading] = useState(false),
    [materialBusy, setMaterialBusy] = useState(null),
    [materialError, setMaterialError] = useState(""),
    [evidenceWidth, setEvidenceWidth] = useState(420),
    [chatExpanded, setChatExpanded] = useState(false);
  const [selectedConceptOption, setSelectedConceptOption] = useState(null),
    [conceptCheckHintVisible, setConceptCheckHintVisible] = useState(false),
    [showLearningSummary, setShowLearningSummary] = useState(false);
  const endRef = useRef(null),
    learningPathRef = useRef(null),
    pending = useRef(null),
    reflectionPending = useRef(null),
    inputRef = useRef(null),
    summaryFormRef = useRef(null),
    summaryInputRef = useRef(null),
    focusComposerAfterReply = useRef(false),
    evidenceResize = useRef(null);
  const currentLearningStep = attempt?.engine_state?.socratic?.learning_step_index ?? 0;
  useEffect(() => {
    const list = learningPathRef.current;
    const current = list?.querySelector('[aria-current="step"]');
    if (!current) return;
    list.scrollTop = Math.max(0, current.offsetTop - list.offsetTop - (list.clientHeight - current.clientHeight) / 2);
  }, [currentLearningStep, assignment?.id, attempt?.id]);
  useEffect(() => {
    let active = true;
    setLoaded(false);
    setAssignment(null);
    setAttempt(null);
    setMaterials([]);
    setMaterialError("");
    setSelectedEvidence(null);
    setShowLearningSummary(false);
    setFinalFeedbackBusy(false);
    pending.current = null;
    Promise.all([
      api(`/platform/assignments/${id}`),
      api(`/platform/assignments/${id}/attempt`),
    ])
      .then(([a, t]) => {
        if (active) {
          setAssignment(a);
          setAttempt(t);
          setLoaded(true);
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [id]);
  useEffect(() => {
    if (assignment?.tool !== "socratic") return;
    let active = true;
    setMaterialsLoading(true);
    api(`/platform/assignments/${id}/materials`)
      .then((result) => { if (active) setMaterials(result.materials || []); })
      .catch((failure) => { if (active) setMaterialError(failure.message); })
      .finally(() => { if (active) setMaterialsLoading(false); });
    return () => { active = false; };
  }, [id, assignment?.tool]);
  useEffect(() => {
    if (attempt)
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [attempt?.messages?.length, outgoingMessage]);
  useEffect(() => {
    if (busy || !focusComposerAfterReply.current) return;
    focusComposerAfterReply.current = false;
    const input = inputRef.current;
    if (!input || input.disabled) return;
    input.focus({ preventScroll: true });
    input.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [busy, attempt?.messages?.length]);
  useEffect(() => {
    if (!showLearningSummary && attempt?.engine_state?.socratic?.phase !== "awaiting_reflection") return;
    summaryFormRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
    summaryInputRef.current?.focus({ preventScroll: true });
  }, [showLearningSummary, attempt?.engine_state?.socratic?.phase]);
  useEffect(() => {
    if (!generationStartedAt) return;
    const update = () =>
      setGenerationSeconds((Date.now() - generationStartedAt) / 1000);
    update();
    const timer = window.setInterval(update, 100);
    return () => window.clearInterval(timer);
  }, [generationStartedAt]);
  useEffect(() => {
    setSelectedEvidence(null);
  }, [attempt?.engine_state?.sources]);
  async function downloadMaterial(material) {
    setMaterialBusy(material.document_id);
    setMaterialError("");
    try {
      const response = await fetch(`/api/platform/assignments/${id}/materials/${encodeURIComponent(material.document_id)}/download`, {
        headers: { Authorization: `Bearer ${session()?.access_token || ""}` },
      });
      if (!response.ok) throw new Error("The original file is unavailable. Please ask your instructor to upload it again.");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = material.title;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (failure) {
      setMaterialError(failure.message);
    } finally {
      setMaterialBusy(null);
    }
  }
  const conceptCheckId =
    attempt?.engine_state?.socratic?.concept_check?.id || null;
  useEffect(() => {
    setSelectedConceptOption(null);
    setConceptCheckHintVisible(false);
  }, [conceptCheckId]);
  useEffect(() => {
    document.body.classList.toggle(
      "evidence-workspace-open",
      Boolean(selectedEvidence),
    );
    return () => document.body.classList.remove("evidence-workspace-open");
  }, [selectedEvidence]);
  useEffect(() => {
    document.body.classList.toggle(
      "socratic-workspace-open",
      assignment?.tool === "socratic",
    );
    return () => document.body.classList.remove("socratic-workspace-open");
  }, [assignment?.tool]);
  useEffect(() => {
    if (assignment?.tool !== "reflections") return;
    let active = true;
    const refresh = () =>
      api(`/platform/assignments/${id}/attempt`)
        .then((value) => {
          if (active) setAttempt(value);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    window.addEventListener("focus", refresh);
    return () => {
      active = false;
      window.removeEventListener("focus", refresh);
    };
  }, [id, assignment?.tool]);
  async function perform(path, body, onResult) {
    setBusy(true);
    setError("");
    try {
      const result = await api(`/platform/assignments/${id}/${path}`, {
        method: "POST",
        body,
      });
      setAttempt(result);
      onResult?.(result);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function send(e) {
    e.preventDefault();
    await sendMessage(message.trim());
  }
  async function sendMessage(
    text,
    clarificationIndex = null,
    conceptCheckOption = null,
  ) {
    if (!text || busy) return;
    const fromComposer =
      clarificationIndex === null &&
      conceptCheckOption === null &&
      message.trim() === text;
    if (
      !pending.current ||
      pending.current.message !== text ||
      (pending.current.clarification_index ?? null) !== clarificationIndex ||
      (pending.current.concept_check_option ?? null) !== conceptCheckOption
    )
      pending.current = {
        message: text,
        request_id: crypto.randomUUID(),
        ...(clarificationIndex !== null
          ? { clarification_index: clarificationIndex }
          : {}),
        ...(conceptCheckOption !== null
          ? { concept_check_option: conceptCheckOption }
          : {}),
      };
    const startedAt = Date.now();
    if (clarificationIndex === null) {
      setOutgoingMessage({
        role: "user",
        content: text,
        created_at: new Date(startedAt).toISOString(),
      });
    }
    if (fromComposer) setMessage("");
    focusComposerAfterReply.current = true;
    setGenerationStartedAt(startedAt);
    setGenerationSeconds(0);
    setLastGenerationSeconds(null);
    let awaitingClarification = false;
    const sent = await perform("messages", pending.current, (result) => {
      awaitingClarification = Boolean(
        result.engine_state?.socratic?.pending_clarification?.inline,
      );
    });
    setOutgoingMessage(null);
    setLastGenerationSeconds(sent && !awaitingClarification ? (Date.now() - startedAt) / 1000 : null);
    setGenerationStartedAt(null);
    if (sent) {
      setMessage("");
      pending.current = null;
    } else if (fromComposer) {
      setMessage(text);
    }
  }
  async function submitConceptCheck(optionIndex) {
    if (busy) return;
    setSelectedConceptOption(optionIndex);
    const option = attempt?.engine_state?.socratic?.concept_check?.options?.[optionIndex];
    if (!option) return;
    if (pending.current?.concept_check_option !== optionIndex) {
      pending.current = {
        message: option.text,
        request_id: crypto.randomUUID(),
        concept_check_option: optionIndex,
      };
    }
    if (await perform("messages", pending.current)) pending.current = null;
  }
  async function finishLearningSummary(event) {
    event.preventDefault();
    const summary = studentReflection.trim();
    if (!summary || busy) return;
    if (
      !reflectionPending.current ||
      reflectionPending.current.summary !== summary
    )
      reflectionPending.current = { summary, request_id: crypto.randomUUID() };
    const startedAt = Date.now();
    setFinalFeedbackBusy(true);
    setGenerationStartedAt(startedAt);
    setGenerationSeconds(0);
    try {
      const sent = await perform("reflection", reflectionPending.current);
      setLastGenerationSeconds(sent ? (Date.now() - startedAt) / 1000 : null);
      if (sent) {
        setStudentReflection("");
        reflectionPending.current = null;
      }
    } finally {
      setGenerationStartedAt(null);
      setFinalFeedbackBusy(false);
    }
  }
  function clampEvidenceWidth(width) {
    return Math.min(Math.max(320, width), maximumEvidenceWidth());
  }
  function startEvidenceResize(event) {
    if (window.innerWidth <= 760) return;
    evidenceResize.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startWidth: evidenceWidth,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    document.body.classList.add("is-resizing-evidence");
  }
  function resizeEvidence(event) {
    const resize = evidenceResize.current;
    if (!resize || resize.pointerId !== event.pointerId) return;
    setEvidenceWidth(
      clampEvidenceWidth(resize.startWidth + resize.startX - event.clientX),
    );
  }
  function stopEvidenceResize(event) {
    if (evidenceResize.current?.pointerId !== event.pointerId) return;
    evidenceResize.current = null;
    document.body.classList.remove("is-resizing-evidence");
  }
  function resizeEvidenceWithKeyboard(event) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Home") setEvidenceWidth(320);
    else if (event.key === "End")
      setEvidenceWidth(clampEvidenceWidth(window.innerWidth));
    else
      setEvidenceWidth((width) =>
        clampEvidenceWidth(width + (event.key === "ArrowLeft" ? 24 : -24)),
      );
  }
  if (!loaded)
    return (
      <>
        <Link to="/student">← Dashboard</Link>
        <Notice error={error} />
        {!error && <p>Opening assignment…</p>}
      </>
    );
  const tool = TOOLS[assignment.tool],
    completed = attempt?.status === "completed",
    state = attempt?.engine_state || {};
  const socratic = state.socratic || {};
  const inlineClarification = socratic.pending_clarification?.inline
    ? socratic.pending_clarification
    : null;
  const conceptCheck = socratic.concept_check || null;
  const thinkingStep =
    assignment.tool === "socratic"
      ? socratic.next_thinking_step || nextQuestion(attempt?.messages)
      : "";
  const keywords = socratic.keywords?.length
    ? socratic.keywords
    : socratic.active_concept
      ? [socratic.active_concept]
      : [];
  const latestAssistantIndex = attempt?.messages
    ? attempt.messages.findLastIndex((item) => item.role === "assistant")
    : -1;
  const hasDiscussedCurrentStep = attempt?.messages?.slice(socratic.step_started_at_message_count || 0)
    .some((item) => item.role === "user");
  const stepActionDisabled = busy || socratic.phase !== "teaching" ||
    Boolean(socratic.pending_clarification || socratic.concept_check) || !hasDiscussedCurrentStep;
  const learningStepCount = assignment.student_config?.learning_steps?.length || 0;
  const activeLearningStep = Math.min(Math.max(Number(socratic.learning_step_index) || 0, 0), Math.max(learningStepCount - 1, 0));
  const finalLearningStepFinished = Boolean(attempt && learningStepCount && activeLearningStep === learningStepCount - 1 && (
    showLearningSummary || attempt.status === "completed" || ["awaiting_reflection", "ready_to_submit"].includes(socratic.phase)
  ));
  const completedLearningSteps = attempt ? Math.min(learningStepCount, activeLearningStep + Number(finalLearningStepFinished)) : 0;
  const milestone =
    assignment.student_config?.module_type === "milestone_based";
  return (
    <>
      <Link className="back" to="/student">
        ← Dashboard
      </Link>
      <div className="page-heading">
        <div>
          <p className="context">{tool.name}</p>
          <h1>{assignment.title}</h1>
          <p className="student-session-identity" aria-label="Student name">
            Student: <strong>{studentName}</strong>
          </p>
          <p>
            {assignment.due_at
              ? `Due ${date(assignment.due_at)}`
              : "Work at your own pace"}
          </p>
        </div>
        <Badge value={attempt?.status || "not_started"} />
      </div>
      <Notice error={error} />
      <div
        className={`workspace-grid${assignment.tool === "socratic" ? " socratic-workspace" : ""}${selectedEvidence ? " evidence-open" : ""}${chatExpanded ? " chat-expanded" : ""}${conceptCheck ? " concept-check-active" : ""}`}
        style={
          selectedEvidence
            ? { "--evidence-drawer-width": `${evidenceWidth}px` }
            : undefined
        }
      >
        <aside className="assignment-info">
          <h2>Your assignment</h2>
          <div className="prose">
            <Markdown>
              {assignment.instructions ||
                "Follow the prompts in this learning activity."}
            </Markdown>
          </div>
          {assignment.tool === "socratic" && (
            <>
              {assignment.student_config?.learning_steps?.length > 0 && (
                <section className="student-learning-path" aria-labelledby="student-learning-path-title">
                  <h3 id="student-learning-path-title">Your learning path</h3>
                  <p className="help">Follow these steps from beginning to end. You can ask the tutor questions about any step.</p>
                  <div className="student-learning-progress">
                    <p>{completedLearningSteps} of {learningStepCount} steps complete{attempt && completedLearningSteps < learningStepCount ? ` · Stage ${activeLearningStep + 1} of ${learningStepCount}` : ""}</p>
                    <div role="progressbar" aria-label="Learning path progress" aria-valuemin={0} aria-valuemax={learningStepCount} aria-valuenow={completedLearningSteps}>
                      <span style={{ width: `${Math.round(completedLearningSteps / learningStepCount * 100)}%` }} />
                    </div>
                  </div>
                  <ol ref={learningPathRef} aria-label="Learning path steps" tabIndex={0}>
                    {assignment.student_config.learning_steps.map((step, index) => {
                      const completed = attempt && (index < activeLearningStep || (finalLearningStepFinished && index === activeLearningStep));
                      const current = attempt && attempt.status !== "completed" && !finalLearningStepFinished && index === activeLearningStep;
                      return (
                        <li key={`${index}-${step.title}`} className={current ? "is-current" : ""} aria-current={current ? "step" : undefined}>
                          {current && <span className="student-step-active-label">Current step</span>}
                          <div className="student-step-title">
                            <strong>{step.title}</strong>
                            {completed && <span className="student-step-complete-icon" role="img" aria-label="Completed step">✓</span>}
                          </div>
                          <span>{step.goal}</span>
                        </li>
                      );
                    })}
                  </ol>
                  {attempt && attempt.status !== "completed" && !showLearningSummary &&
                    (activeLearningStep < learningStepCount - 1 ? (
                      <button type="button" className="compact next-learning-step" disabled={stepActionDisabled} onClick={() => perform("next-step", {})}>
                        Continue to next step
                      </button>
                    ) : socratic.phase !== "ready_to_submit" && (
                      <button type="button" className="compact next-learning-step" disabled={stepActionDisabled} onClick={() => setShowLearningSummary(true)}>
                        Finish conversation and summarize
                      </button>
                    ))}
                </section>
              )}
              <section className="student-course-materials" aria-labelledby="student-course-materials-title">
                <h3 id="student-course-materials-title">Course materials</h3>
                <p className="help">Download the original documents your instructor selected for this assignment.</p>
                {materialError && <p className="help" role="alert">{materialError}</p>}
                {materialsLoading ? <p className="help" role="status">Loading course materials…</p> : materials.length ? <ul>
                  {materials.map((material) => <li key={material.document_id}>
                    {material.original_available ? <button type="button" className="quiet" onClick={() => downloadMaterial(material)} disabled={materialBusy === material.document_id}>
                      {materialBusy === material.document_id ? "Downloading…" : `Download ${material.title}`}
                    </button> : <span>{material.title} · Original file unavailable</span>}
                  </li>)}
                </ul> : !materialError && <p className="help">No published documents are available.</p>}
              </section>
              {assignment.student_config?.keyword_glossary?.length > 0 && (
                <section
                  className="student-keyword-glossary"
                  aria-labelledby="student-keyword-glossary-title"
                >
                  <h3 id="student-keyword-glossary-title">Key concepts</h3>
                  <p className="help">
                    Review these instructor-approved terms before you begin.
                  </p>
                  <dl>
                    {assignment.student_config.keyword_glossary.map((entry) => (
                      <div key={entry.keyword}>
                        <dt>{entry.keyword}</dt>
                        <dd>{entry.definition}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}
              <p className="help">
                Work through the tutor's questions, then summarize what you
                learned in your own words. Review the final feedback before
                submitting.
              </p>
            </>
          )}
          {assignment.tool === "debate" && (
            <>
              {attempt?.messages?.[0]?.content?.trim() !==
                assignment.student_config.scenario.trim() && (
                <>
                  <h3>Scenario</h3>
                  <div className="prose">
                    <Markdown>{assignment.student_config.scenario}</Markdown>
                  </div>
                </>
              )}
              <p className="help">
                Defend your position across at least{" "}
                {assignment.student_config.minimum_messages} response(s), then
                mark the assignment complete.
              </p>
            </>
          )}
          {assignment.tool === "reflections" && (
            <p className="help">
              {milestone
                ? "Submit your milestone reflection to complete this assignment."
                : "Reflect on the prompts, then finish the session to receive your evaluation."}
            </p>
          )}
          {assignment.tool === "student-agent" && (
            <>
              <h3>{assignment.student_config.topic_name}</h3>
              <ul className="resources">
                {assignment.student_config.resources.map((r, i) => (
                  <li key={i}>
                    <a href={r.url} target="_blank" rel="noreferrer">
                      {r.title}
                    </a>
                  </li>
                ))}
              </ul>
              <p className="help">
                Work through reading, discussion, and practice. Complete the
                assignment at wrap-up.
              </p>
            </>
          )}
          {attempt && !completed && assignment.tool !== "reflections" && (
            <>
              <p className="saved-note">
                Progress is saved after each response. You can return to your
                dashboard at any time.
              </p>
              {!milestone && (
                <button
                  className={assignment.tool === "socratic" && socratic.phase === "ready_to_submit"
                    ? "submit-assignment-ready"
                    : "secondary"}
                  disabled={
                    busy ||
                    (assignment.tool === "socratic" &&
                      socratic.phase !== "ready_to_submit")
                  }
                  onClick={() => perform("complete")}
                >
                  {assignment.tool === "socratic"
                    ? "Submit assignment"
                    : assignment.tool === "reflections"
                      ? "Finish reflection & evaluate"
                      : "Mark assignment complete"}
                </button>
              )}
            </>
          )}
        </aside>
        <section className="chat-panel" aria-label={`${tool.name} assignment`}>
          <div className="chat-heading">
            <span className="tool-mark" style={{ "--tool-color": tool.color }}>
              {tool.short}
            </span>
            <div>
              <h2>{tool.name}</h2>
              <p>
                {state.phase_label ||
                  (state.total_questions
                    ? `Question ${Math.min((state.question_index || 0) + 1, state.total_questions)} of ${state.total_questions}`
                    : tool.description)}
              </p>
            </div>
            {assignment.tool === "socratic" &&
              !selectedEvidence &&
              !conceptCheck && (
                <button
                  type="button"
                  className="secondary compact chat-expand-control"
                  aria-pressed={chatExpanded}
                  aria-label={chatExpanded ? "Show assignment" : "Expand chat"}
                  title={chatExpanded ? "Show assignment" : "Expand chat"}
                  onClick={() => setChatExpanded((expanded) => !expanded)}
                >
                  {chatExpanded ? (
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M9 3v6H3M15 3v6h6M9 21v-6H3M15 21v-6h6" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M9 3H3v6M15 3h6v6M9 21H3v-6M15 21h6v-6" />
                    </svg>
                  )}
                </button>
              )}
          </div>
          {assignment.tool === "reflections" ? (
            <div className="start-state">
              <h2>
                {completed
                  ? "Your reflection is complete."
                  : "Ready when you are."}
              </h2>
              <p>
                Open Reflections in a new tab. Your professor’s settings and
                saved progress are loaded automatically.
              </p>
              <a
                className="button"
                href={`/platform/reflections.html?assignment=${encodeURIComponent(id)}`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={async (event) => {
                  event.preventDefault();
                  const tab = window.open("about:blank", "_blank");
                  if (!tab) {
                    setError("Allow pop-ups to open Reflections, then retry.");
                    return;
                  }
                  tab.opener = null;
                  try {
                    const { code } = await api(
                      `/platform/assignments/${encodeURIComponent(id)}/reflection-launch`,
                      { method: "POST" },
                    );
                    tab.location.replace(
                      `/platform/reflections.html?assignment=${encodeURIComponent(id)}#code=${encodeURIComponent(code)}`,
                    );
                  } catch (error) {
                    tab.close();
                    setError(error.message);
                  }
                }}
              >
                {completed
                  ? "View reflection results"
                  : attempt
                    ? "Resume assignment"
                    : "Start assignment"}
              </a>
            </div>
          ) : !attempt ? (
            <div className="start-state">
              <h2>Ready when you are.</h2>
              <p>
                Your professor’s settings are already loaded. Start to open your
                learning session.
              </p>
              <button disabled={busy} onClick={() => perform("start")}>
                {busy ? "Starting…" : "Start assignment"}
              </button>
            </div>
          ) : (
            <>
              <div className="messages" aria-live="polite" aria-busy={busy}>
                {attempt.messages.map((m, i) =>
                  assignment.tool === "socratic" ? (
                    <SocraticMessage
                      key={i}
                      studentName={studentName}
                      message={m}
                      latest={i === latestAssistantIndex && !inlineClarification}
                      thinkingStep={thinkingStep}
                      keywords={keywords}
                      sources={state.sources}
                      responseSeconds={lastGenerationSeconds}
                      selectedEvidence={selectedEvidence}
                      setSelectedEvidence={setSelectedEvidence}
                    />
                  ) : (
                    <article className={`message ${m.role}`} key={i}>
                      <span className="message-author">
                        {m.role === "user" ? studentName : tool.name}
                      </span>
                      <div className="prose">
                        <Markdown>{m.content}</Markdown>
                      </div>
                      {assignment.tool === "debate" &&
                        m.role === "assistant" &&
                        i === latestAssistantIndex &&
                        state.sources?.length > 0 && (
                          <div className="message-evidence">
                            <strong>Course evidence</strong>
                            <div>
                              {state.sources.map((source, index) => (
                                <button
                                  type="button"
                                  className="evidence-chip"
                                  key={source.chunk_id || index}
                                  aria-pressed={
                                    selectedEvidence?.chunk_id ===
                                    source.chunk_id
                                  }
                                  aria-controls="evidence-document-drawer"
                                  aria-expanded={
                                    selectedEvidence?.chunk_id ===
                                    source.chunk_id
                                  }
                                  onClick={() =>
                                    setSelectedEvidence((current) =>
                                      current?.chunk_id === source.chunk_id
                                        ? null
                                        : source,
                                    )
                                  }
                                >
                                  {source.title}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                    </article>
                  ),
                )}
                {busy && outgoingMessage &&
                  (assignment.tool === "socratic" ? (
                    <SocraticMessage
                      message={outgoingMessage}
                      studentName={studentName}
                      isPending
                    />
                  ) : (
                    <article className="message user is-pending">
                      <span className="message-author">
                        {studentName} · Sending…
                      </span>
                      <div className="prose">
                        <Markdown>{outgoingMessage.content}</Markdown>
                      </div>
                    </article>
                  ))}
                {busy && !finalFeedbackBusy &&
                  (assignment.tool === "socratic" ? (
                    <SocraticThinkingMessage
                      elapsedSeconds={
                        generationStartedAt ? generationSeconds : 0
                      }
                    />
                  ) : (
                    <GenerationStatus
                      title={TOOLS[assignment.tool]?.name || "BrainTutor"}
                      message="Working on your response…"
                      messageCard
                    />
                  ))}
                {assignment.tool === "socratic" &&
                  inlineClarification &&
                  !completed &&
                  !busy && (
                    <div className="intent-confirmation" role="group" aria-label="Clarify your question">
                      <span className="intent-confirmation-label">Quick check before I answer</span>
                      <p>{inlineClarification.question}</p>
                      <div className="intent-confirmation-options">
                        {socratic.clarification_options?.map((option, index) => (
                          <button
                            type="button"
                            className="suggestion-chip"
                            key={index}
                            onClick={() => sendMessage(option.label, index)}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                <div ref={endRef} />
              </div>
              {!completed && assignment.tool === "student-agent" && (
                <div className="tutor-controls">
                  {state.nav?.map((n) => (
                    <button
                      key={n.id}
                      disabled={busy || !n.unlocked || n.current}
                      className="secondary compact"
                      onClick={() =>
                        perform("actions", {
                          action: "navigate",
                          value: n.id,
                          request_id: crypto.randomUUID(),
                        })
                      }
                    >
                      {n.label}
                    </button>
                  ))}
                  {state.awaiting_scenario && (
                    <div>
                      <p>Choose a practice scenario:</p>
                      {state.practice_options?.map((s) => (
                        <button
                          className="secondary compact"
                          key={s}
                          disabled={busy}
                          onClick={() =>
                            perform("actions", {
                              action: "scenario",
                              value: s,
                              request_id: crypto.randomUUID(),
                            })
                          }
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {assignment.tool === "socratic" &&
                socratic.clarification_options?.length > 0 &&
                !inlineClarification &&
                !conceptCheck &&
                !completed && (
                  <div
                    className="suggested-responses"
                    aria-label="Clarify what you mean"
                  >
                    {socratic.clarification_options.map((option, index) => (
                      <button
                        key={index}
                        className="suggestion-chip"
                        disabled={busy}
                        onClick={() => sendMessage(option.label, index)}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                )}
              {assignment.tool === "socratic" && conceptCheck && !completed && (
                <ConceptCheck
                  check={conceptCheck}
                  selectedOption={selectedConceptOption}
                  busy={busy}
                  hintVisible={conceptCheckHintVisible}
                  onShowHint={() =>
                    setConceptCheckHintVisible((visible) => !visible)
                  }
                  onSelect={submitConceptCheck}
                />
              )}
              {assignment.tool === "socratic" && socratic.concept_check_response && !conceptCheck && (
                <div className="concept-check concept-check-feedback" role="status">
                  <strong>{socratic.concept_check_response.correct ? "Correct—this example applies the concept." : "Not quite—review the best example below."}</strong>
                  {!socratic.concept_check_response.correct && (
                    <p>{socratic.concept_check_response.correct_option?.text}</p>
                  )}
                  <p>Continue the discussion when you are ready.</p>
                </div>
              )}
              {assignment.tool === "socratic" && (
                <SocraticLearningSummary
                  summary={socratic.completion_summary}
                />
              )}
              {!completed &&
                assignment.tool === "socratic" &&
                !assignment.student_config?.learning_steps?.length &&
                socratic.phase === "teaching" &&
                !showLearningSummary &&
                !conceptCheck &&
                !inlineClarification &&
                attempt.messages.some((item) => item.role === "user") && (
                  <button
                    type="button"
                    className="secondary compact"
                    disabled={busy}
                    onClick={() => setShowLearningSummary(true)}
                  >
                    Finish conversation and summarize
                  </button>
                )}
              {completed ? (
                <Result result={attempt.result || {}} />
              ) : assignment.tool === "socratic" &&
                (socratic.phase === "awaiting_reflection" ||
                  (socratic.phase === "teaching" && showLearningSummary)) ? (
                <form
                  ref={summaryFormRef}
                  className={`composer learning-reflection-form${finalLearningStepFinished ? " is-highlighted" : ""}`}
                  onSubmit={finishLearningSummary}
                >
                  {finalLearningStepFinished && <p className="summary-focus-label">Final step complete · Summarize your learning</p>}
                  <label htmlFor="student-learning-summary">
                    Summarize what you learned in your own words
                  </label>
                  <p className="help">
                    Explain the original question using the example from your
                    conversation.
                  </p>
                  <textarea
                    id="student-learning-summary"
                    ref={summaryInputRef}
                    value={studentReflection}
                    maxLength={4000}
                    rows={5}
                    disabled={busy}
                    onChange={(event) =>
                      setStudentReflection(event.target.value)
                    }
                  />
                  <button disabled={busy || !studentReflection.trim()}>
                    Get final feedback
                  </button>
                  {socratic.phase === "teaching" && (
                    <button
                      type="button"
                      className="secondary compact"
                      disabled={busy}
                      onClick={() => setShowLearningSummary(false)}
                    >
                      Keep chatting
                    </button>
                  )}
                </form>
              ) : assignment.tool === "socratic" &&
                socratic.phase === "ready_to_submit" ? (
                <p className="notice">
                  Review your learning summary, then select Submit assignment.
                </p>
              ) : conceptCheck ? null : (
                <form className="composer" onSubmit={send}>
                  <label className="sr-only" htmlFor="reply">
                    Your {milestone ? "reflection" : "message"}
                  </label>
                  <textarea
                    id="reply"
                    ref={inputRef}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    disabled={busy}
                    rows={milestone ? 7 : 3}
                    maxLength={20000}
                    placeholder={
                      milestone
                        ? "Write your reflection…"
                        : "Share your thinking…"
                    }
                    onKeyDown={(e) => {
                      if (
                        e.key === "Enter" &&
                        !e.shiftKey &&
                        !e.nativeEvent.isComposing
                      ) {
                        e.preventDefault();
                        send(e);
                      }
                    }}
                  />
                  <div>
                    <span className="help">
                      {milestone
                        ? "Submitting completes this assignment."
                        : "Enter to send · Shift + Enter for a new line"}
                    </span>
                    <button disabled={busy || !message.trim()}>
                      {milestone ? "Submit reflection" : "Send message"}
                    </button>
                  </div>
                </form>
              )}
            </>
          )}
        </section>
      </div>
      <EvidenceDrawer
        assignmentId={id}
        evidence={selectedEvidence}
        keywords={keywords}
        width={evidenceWidth}
        onClose={() => setSelectedEvidence(null)}
        onResizeStart={startEvidenceResize}
        onResize={resizeEvidence}
        onResizeEnd={stopEvidenceResize}
        onResizeKeyDown={resizeEvidenceWithKeyboard}
      />
      {finalFeedbackBusy && <GenerationStatus
        message="Evaluating your learning summary and preparing final feedback…"
        elapsedSeconds={generationSeconds}
        ariaLabel="BrainTutor is preparing final feedback"
        fullScreen
      />}
    </>
  );
}
