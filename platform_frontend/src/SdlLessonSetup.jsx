import React from "react";

import "./sdl-lesson-setup.css";

export default function SdlLessonSetup({
  value,
  onChange,
  disabled = false,
  canSuggest = false,
  onSuggest,
  suggestions,
  onSuggestionsChange,
  onConfirmSuggestions,
}) {
  const update = (key, next) => onChange({ ...value, [key]: next });

  return (
    <div className="sdl-lesson-setup">
      <header className="sdl-lesson-setup-intro">
        <h2>Create a learning lesson</h2>

        <p>
          Tell us what students should learn. You can provide as much or as
          little detail as you like.
        </p>
      </header>

      <fieldset disabled={disabled}>
        <legend>
          <span aria-hidden="true">1</span> What should students learn?
        </legend>

        <label>
          Learning focus
          <textarea
            rows={3}
            maxLength={10000}
            value={value.prompt || ""}
            onChange={(e) => update("prompt", e.target.value)}
            placeholder="e.g., Understand how Scrum teams plan and manage work during a Sprint."
          />
        </label>

        <label>
          What specific concepts should the lesson cover?{" "}
          <span className="sdl-optional">(Optional)</span>
          <textarea
            aria-label="What specific concepts should the lesson cover?"
            rows={3}
            value={(value.custom_questions || []).join("\n")}
            onChange={(e) =>
              update("custom_questions", e.target.value.split("\n"))
            }
            placeholder="e.g., Sprint Planning, Daily Scrum, Sprint Review, Sprint Retrospective, and the responsibilities of Scrum team members."
          />
        </label>

        <p className="help">
          Add concepts or questions you want covered, one per line.
        </p>
      </fieldset>

      <fieldset disabled={disabled}>
        <legend>
          <span aria-hidden="true">2</span> What do students already know?{" "}
          <span className="sdl-optional">(Optional)</span>
        </legend>

        <label className="sr-only" htmlFor="sdl-starting-point">
          What do students already know?
        </label>

        <textarea
          id="sdl-starting-point"
          rows={3}
          maxLength={2000}
          value={value.starting_point || ""}
          onChange={(e) => update("starting_point", e.target.value)}
          placeholder="e.g., Students understand basic software development and teamwork but have little experience with Scrum."
        />
      </fieldset>

      <fieldset disabled={disabled}>
        <legend>
          <span aria-hidden="true">3</span> What should students be able to do
          by the end? <span className="sdl-optional">(Optional)</span>
        </legend>

        <label className="sr-only" htmlFor="sdl-ending-point">
          What should students be able to do by the end?
        </label>

        <textarea
          id="sdl-ending-point"
          rows={3}
          maxLength={4000}
          value={value.ending_point || ""}
          onChange={(e) => update("ending_point", e.target.value)}
          placeholder="e.g., Explain Scrum events, distinguish team accountabilities, and apply Scrum principles to realistic project situations."
        />
      </fieldset>

      <fieldset disabled={disabled}>
        <legend>
          <span aria-hidden="true">4</span> Additional instructions{" "}
          <span className="sdl-optional">(Optional)</span>
        </legend>

        <label className="sr-only" htmlFor="sdl-additional-instructions">
          Additional instructions
        </label>

        <p className="help">
          Guides AI lesson generation. This is not shown as the student-facing
          assignment description.
        </p>

        <textarea
          id="sdl-additional-instructions"
          rows={3}
          maxLength={10000}
          value={value.additional_instructions || ""}
          onChange={(e) => update("additional_instructions", e.target.value)}
          placeholder="Any specific examples, readings, terminology, or teaching preferences?"
        />
      </fieldset>

      {suggestions &&
        (!value.starting_point?.trim() || !value.ending_point?.trim()) && (
          <section
            className="sdl-boundary-review"
            aria-label="Suggested lesson details"
          >
            <h3>Review lesson details</h3>
            <p className="sdl-suggestion-label">
              AI-generated suggestions · review and edit
            </p>

            {!value.starting_point?.trim() && (
              <label>
                Suggested prior knowledge
                <textarea
                  rows={3}
                  maxLength={2000}
                  disabled={disabled}
                  value={suggestions.starting_point || ""}
                  onChange={(e) =>
                    onSuggestionsChange({
                      ...suggestions,
                      starting_point: e.target.value,
                    })
                  }
                />
              </label>
            )}

            {!value.ending_point?.trim() && (
              <label>
                Suggested end goal
                <textarea
                  rows={3}
                  maxLength={4000}
                  disabled={disabled}
                  value={suggestions.ending_point || ""}
                  onChange={(e) =>
                    onSuggestionsChange({
                      ...suggestions,
                      ending_point: e.target.value,
                    })
                  }
                />
              </label>
            )}

            <button
              type="button"
              disabled={
                disabled ||
                (!value.starting_point?.trim() &&
                  !suggestions.starting_point?.trim()) ||
                (!value.ending_point?.trim() &&
                  !suggestions.ending_point?.trim())
              }
              onClick={onConfirmSuggestions}
            >
              Confirm lesson details
            </button>

            <button
              type="button"
              className="secondary"
              disabled={disabled || !canSuggest}
              onClick={onSuggest}
            >
              Suggest again
            </button>
          </section>
        )}

      <p className="sdl-lesson-review-note">
        Review the generated lesson before publishing.
      </p>
    </div>
  );
}
