-- LC 1280 · Students and Examinations
--
-- Every student paired with every subject, and how many times that student
-- attended that subject's exam, including 0. Ordered by student id, then subject.
--
-- The four questions:
-- 1. Which join gives every student-subject combination? A CROSS JOIN: every row of
--    students with every row of subjects, no condition (3 × 3 = 9 rows here).
-- 2. How do students with no exams still appear? A LEFT JOIN from those combinations
--    to examinations keeps every combination, with NULLs where nothing matches.
-- 3. count(*) or count(column)? count(e.student_id): it counts only non-NULL values,
--    so an unmatched combination counts 0. count(*) counts the row itself, giving 1.
-- 4. What to GROUP BY? Each combination (student id, name, subject), so a student's
--    three Biology attempts become one row with 3.

SELECT
    s.student_id,
    s.student_name,
    sub.subject_name,
    count(e.student_id) AS attended_exams
FROM students AS s
CROSS JOIN subjects AS sub
LEFT JOIN examinations AS e
    ON e.student_id = s.student_id
   AND e.subject_name = sub.subject_name
GROUP BY s.student_id, s.student_name, sub.subject_name
ORDER BY s.student_id, sub.subject_name;
