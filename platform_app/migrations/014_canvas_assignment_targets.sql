-- Exact Canvas API targets. A missing course ID requires instructor input at deletion.
CREATE TABLE canvas_assignment_targets_platform (
    assignment_id UUID PRIMARY KEY REFERENCES assignments_platform(id) ON DELETE CASCADE,
    canvas_course_id BIGINT CHECK (canvas_course_id > 0),
    canvas_assignment_id BIGINT NOT NULL CHECK (canvas_assignment_id > 0),
    source TEXT NOT NULL CHECK (source IN ('lti', 'import')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (canvas_course_id, canvas_assignment_id)
);

INSERT INTO canvas_assignment_targets_platform (assignment_id, canvas_assignment_id, source)
SELECT assignment_id, canvas_assignment_id::BIGINT, 'lti'
FROM lti_assignment_links_platform
WHERE canvas_assignment_id ~ '^[0-9]{1,18}$'
  AND canvas_assignment_id::BIGINT > 0
ON CONFLICT DO NOTHING;
