# SDL UI reference

SDL presentation uses the committed sdl-teaching-preview stylesheet at f65d290 as its reference. The copied CSS is scoped to .sdl-teaching-ui, and keyframe names are prefixed with sdl-teaching- to avoid changing other tools. The repeated scope class provides specificity over later shared styles.

The reference applies to the SDL tool dashboard, instructor editor/review, published assignment details, and student lesson workspace. Other tools keep their current containers and styling. The SDL instructor header uses the earlier simpler presentation.

No backend, transport, grading, generation, persistence, or assessment-stage code was changed. The current 3-question / 3-application-section / 2-interview format, optional interview/reporting, material expansion, quality checks, section Edit/Save and bottom Publish controls remain intact.

Verification: 171 existing frontend tests passed. Two additional checks passed for selector/animation isolation and the reference sidebar/responsive layout. The production build passed. Instructor review and student application-stage presentation were visually inspected using synthetic local data, without contacting a real course or modifying assignments.
