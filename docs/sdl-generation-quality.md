# SDL generation quality checks

## Confirmed causes and fixes

- Both quiz adaptation and practice repair previously prepended scenario text unconditionally. A shared composer now avoids repeating identical setup text or sentences. Authoring instructions keep setup in the scenario field and the decision in the question field.
- The inherited EduMind template contained TF/MR examples and inconsistent difficulty names. The model-facing adaptation now uses SDL single-answer MCQs and its configured cognitive levels. Application questions must depend on scenario facts; wrong options should reflect plausible misunderstandings.
- The platform appended instructor sub-questions to learning focus; the bounded authoring path truncated that combined string to a 200-character topic and represented the ending outcome as one objective. The topic is now separated from the full sub-question list.
- New platform drafts preserve instructor outcomes/sub-questions in a coverage table. Every requirement must retain its description and reference existing quiz/application IDs. Publication validation rejects missing/deleted requirements, empty mappings, and invalid references.
- For new drafts, nonempty rubric evidence groups require at least two distinct equivalent examples and cannot copy the criterion verbatim. Empty groups remain valid because AI grading uses criterion descriptions, not mandatory keyword matches.

## Compatibility and limits

These authoring checks are versioned. Previously published snapshots retain their old validation behavior. The section Edit/Save and bottom Publish controls remain wired.

The coverage table is a declared mapping for instructor review. Structural validation does not prove that a referenced task meaningfully assesses the requirement. Likewise, prompt instructions do not prove distractor plausibility or cognitive difficulty. Exact text deduplication does not detect every paraphrase. A fresh real-provider sample and instructor review are still required before claiming improved pedagogical quality. No independent semantic critic has been added.

## Verification

97 targeted mocked-provider/backend checks passed, including quiz and practice composition, requirement preservation, publication rejection, equivalent evidence, legacy compatibility, and authoring input separation. Frontend regression: 171 passed with 13 existing skips; production build passed.
