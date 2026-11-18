import { ACTIVITY_TYPES, TOOLS } from "./api";
import ToolIcon from "./ToolIcon";

export default function ChatbotPicker({ value, onChange }) {
  return (
    <fieldset className="chatbot-picker">
      <legend>Assigned chatbot</legend>
      <p className="help">Choose the experience that fits this assignment.</p>
      <div className="tool-grid">
        {ACTIVITY_TYPES.map((id, index) => {
          const tool = TOOLS[id];
          return (
            <label
              className={`tool-card chatbot-choice${value === id ? " is-selected" : ""}`}
              style={{ "--tool-color": tool.color }}
              key={id}
            >
              <input
                type="radio"
                name="assigned-chatbot"
                value={id}
                checked={value === id}
                aria-label={tool.name}
                onChange={() => onChange(id)}
              />
              <span className="tool-card-topline">
                <span className="tool-mark">
                  <ToolIcon tool={id} />
                </span>
                <span className="tool-step">{String(index + 1).padStart(2, "0")}</span>
              </span>
              <span className="tool-mode">{tool.mode}</span>
              <span className="chatbot-choice-title">{tool.name}</span>
              <span className="chatbot-choice-description">
                {tool.description}
              </span>
              <span className="tool-action">
                {value === id ? "Selected" : "Choose chatbot"}
                <span aria-hidden="true">{value === id ? "✓" : "→"}</span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
