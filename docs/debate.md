# Debate assignments

Debate is a native BrainTutor assignment type for practicing argumentation. An
instructor supplies a scenario, an optional opening prompt, the number of
student responses required before reflection, and a final-reflection prompt.
Course documents are optional.
When documents are available, the instructor may select specific materials or
use all current course materials; their indexed chunks are frozen at publication
and retrieved to ground relevant debate challenges. Without documents, Debate
continues from the scenario and conversation alone. Students open the assignment from
the same dashboard as other BrainTutor work and use the standard persistent
conversation workspace. The saved stage moves from taking a position, through
responding to challenges, to a required final reflection. Students may leave
and resume at any point. Completion is accepted only after the reflection is
saved, and duplicate request IDs do not create duplicate turns or reflections.

The Debate engine uses the chat provider already configured for Socratic Chat.
It challenges a defensible argument as a Devil's Advocate, focusing on one
assumption, evidence gap, counterargument, stakeholder, tradeoff, causal step,
or feasibility issue at a time. When a student explicitly asks for help or has
not formed a usable argument, it switches to brief Student Guide scaffolding.

Debate reuses the platform's authentication, course authorization, immutable
published configuration, one-attempt persistence, request idempotency, progress
reporting, and completion controls. A course instructor can review each assigned
student's saved transcript, stage, reflection, and completion time from the
assignment page. Debate does not add separate join codes, automatic grades,
restarts, or a second AI service.

The instructor review endpoint is `GET /api/platform/assignments/{id}/debate-review`.
It requires professor authority and verified instructor membership in the
assignment's course. Students and instructors from other courses cannot read it.
