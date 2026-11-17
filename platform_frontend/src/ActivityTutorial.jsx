import { useEffect, useRef, useState } from "react";
import { TOOLS } from "./api";

const TOOL_HELP = {
  socratic: "Choose a basic conversation or a guided path. Set the opening question and review any generated steps.",
  reflections: "Set reflection topics or a milestone prompt, then review what students will respond to.",
  "self-directed-learning": "Set the lesson focus and questions; review the generated lesson before publishing.",
  debate: "Write the debate scenario students will see and respond to.",
  aiducate: "Add the activity instructions. This activity can be saved as a draft until its backend is connected.",
};

const STEPS = [
  { target: "title", title: "Assignment title", text: "Give students a clear name for this assignment. Canvas launches can fill this automatically." },
  { target: "due", title: "Due date", text: "Check when this assignment is due. Canvas launches can fill this automatically." },
  { target: "instructions", title: "Student instructions", text: "Tell students what to do and what, if anything, they must submit in Canvas." },
  { target: "materials", title: "Course materials", text: "Upload or select the documents this activity should use. Files must be indexed before they can be selected." },
  { target: "activity", title: "Choose an activity", text: "Pick one learning activity. Its settings will appear below." },
  { target: "settings", title: "Activity settings", text: "Review how students will work through this activity." },
  { target: "publish", title: "Review and publish", text: "Review the setup, publish it, then check the read-only student preview." },
];

export function tutorialPopoverPosition(target, popoverSize, viewport) {
  const padding = 16;
  const gap = 18;
  const width = Math.min(popoverSize.width, viewport.width - padding * 2);
  const height = Math.min(popoverSize.height, viewport.height - padding * 2);
  const clamp = (value, max) => Math.min(Math.max(padding, value), Math.max(padding, max - padding));
  const rightAligned = target.right - width;
  const candidates = [
    { left: target.right + gap, top: target.top },
    { left: target.left - width - gap, top: target.top },
    { left: rightAligned, top: target.bottom + gap },
    { left: rightAligned, top: target.top - height - gap },
  ];
  let best = null;
  for (const candidate of candidates) {
    const left = clamp(candidate.left, viewport.width - width);
    const top = clamp(candidate.top, viewport.height - height);
    const overlapWidth = Math.max(0, Math.min(left + width, target.right) - Math.max(left, target.left));
    const overlapHeight = Math.max(0, Math.min(top + height, target.bottom) - Math.max(top, target.top));
    const overlap = overlapWidth * overlapHeight;
    if (!best || overlap < best.overlap) best = { left, top, overlap };
    if (overlap === 0) break;
  }
  return { left: best.left, top: best.top };
}

export default function ActivityTutorial({ tool, onClose }) {
  const [index, setIndex] = useState(0);
  const [position, setPosition] = useState(null);
  const popover = useRef(null);
  const steps = tool ? STEPS : STEPS.filter((step) => step.target !== "settings");
  const step = steps[Math.min(index, steps.length - 1)];

  useEffect(() => {
    if (index >= steps.length) setIndex(steps.length - 1);
  }, [index, steps.length]);

  useEffect(() => {
    const target = document.querySelector(`[data-activity-tutorial="${step.target}"]`);
    if (!target) return undefined;
    target.classList.add("activity-tutorial-highlight");
    target.scrollIntoView?.({ block: "center", behavior: "smooth" });
    const place = () => {
      const box = target.getBoundingClientRect();
      setPosition(tutorialPopoverPosition(box, {
        width: popover.current?.offsetWidth || 330,
        height: popover.current?.offsetHeight || 190,
      }, { width: window.innerWidth, height: window.innerHeight }));
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    popover.current?.focus({ preventScroll: true });
    return () => {
      target.classList.remove("activity-tutorial-highlight");
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [step.target]);

  useEffect(() => {
    const escape = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [onClose]);

  return <>
    <div className="activity-tutorial-overlay" aria-hidden="true" onClick={onClose} />
    <div
      ref={popover}
      className="activity-tutorial-popover"
      role="dialog"
      aria-label="Assignment tutorial"
      tabIndex={-1}
      style={position || undefined}
    >
      <div className="activity-tutorial-topline">
        <span>Step {index + 1} of {steps.length}</span>
        <button type="button" className="quiet" onClick={onClose} aria-label="Close tutorial">×</button>
      </div>
      <h3>{step.title}</h3>
      <p>{step.target === "settings" ? TOOL_HELP[tool] || `Review ${TOOLS[tool]?.name || "activity"} settings.` : step.text}</p>
      <div className="activity-tutorial-actions">
        <button type="button" className="secondary" disabled={index === 0} onClick={() => setIndex(index - 1)}>Back</button>
        <button type="button" onClick={() => index === steps.length - 1 ? onClose() : setIndex(index + 1)}>{index === steps.length - 1 ? "Finish tutorial" : "Next"}</button>
      </div>
    </div>
  </>;
}
