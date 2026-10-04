ALTER TABLE courses_platform
ADD COLUMN IF NOT EXISTS canvas_course_id TEXT;

-- Only the exact description written by the previous Canvas import qualifies.
-- If a source was imported more than once under different codes, leave later
-- duplicates unmapped so the unique instructor/source relationship is clear.
WITH legacy AS (
    SELECT
        id,
        instructor_id,
        substring(description FROM '^Imported from UNC Charlotte Canvas course ([0-9]+)[.]$') AS source_id,
        row_number() OVER (
            PARTITION BY instructor_id, substring(description FROM '^Imported from UNC Charlotte Canvas course ([0-9]+)[.]$')
            ORDER BY created_at, id
        ) AS source_rank
    FROM courses_platform
    WHERE canvas_course_id IS NULL
      AND description ~ '^Imported from UNC Charlotte Canvas course [0-9]+[.]$'
)
UPDATE courses_platform AS course
SET canvas_course_id = legacy.source_id
FROM legacy
WHERE course.id = legacy.id
  AND legacy.source_rank = 1
  AND NOT EXISTS (
      SELECT 1 FROM courses_platform AS mapped
      WHERE mapped.instructor_id = legacy.instructor_id
        AND mapped.canvas_course_id = legacy.source_id
  );

CREATE UNIQUE INDEX IF NOT EXISTS courses_platform_instructor_canvas_course_id_key
ON courses_platform (instructor_id, canvas_course_id)
WHERE canvas_course_id IS NOT NULL;
