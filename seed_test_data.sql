-- ==========
-- Clean slate (optional; ONLY if you don't care about current data)
-- ==========
DELETE FROM payments;
DELETE FROM student_group;
DELETE FROM students;
DELETE FROM groups;

-- ==========
-- Groups
-- ==========
INSERT OR IGNORE INTO groups(name) VALUES
  ('Group A'),
  ('Group B'),
  ('Group C');

-- ==========
-- Students
-- ==========
-- Four students with fixed IDs so you can recognise them
INSERT INTO students(id, name, join_date) VALUES
  (101, 'Alice', '2024-09-10'),
  (102, 'Sara',  '2024-09-11'),
  (103, 'Omar',  '2024-09-12'),
  (104, 'Lina',  '2024-09-13');

-- ==========
-- Student ↔ Group links
-- ==========
-- Alice  -> Group A
INSERT INTO student_group(student_id, group_id)
SELECT 101, id FROM groups WHERE name = 'Group A';

-- Sara   -> Group A + Group B
INSERT INTO student_group(student_id, group_id)
SELECT 102, id FROM groups WHERE name = 'Group A';
INSERT INTO student_group(student_id, group_id)
SELECT 102, id FROM groups WHERE name = 'Group B';

-- Omar   -> Group B
INSERT INTO student_group(student_id, group_id)
SELECT 103, id FROM groups WHERE name = 'Group B';

-- Lina   -> Group C
INSERT INTO student_group(student_id, group_id)
SELECT 104, id FROM groups WHERE name = 'Group C';

-- ==========
-- Payments for current year/month view test
-- (adjust 2025 / month numbers if you want)
-- ==========
-- We'll use November 2025 like in your screenshot
INSERT INTO payments(student_id, year, month, paid, payment_date) VALUES
  (101, 2025, 11, 'paid',   '2025-11-05'),  -- Alice paid
  (102, 2025, 11, 'unpaid', '2025-11-01'),  -- Sara unpaid
  (103, 2025, 11, 'paid',   '2025-11-03'),  -- Omar paid
  (104, 2025, 11, 'unpaid', '2025-11-02');  -- Lina unpaid

-- ==========
-- Payments for history window (academic year 2024–2025 for Alice only)
-- ==========
-- Academic year 2024: Aug–Dec 2024, Jan–Jul 2025
INSERT INTO payments(student_id, year, month, paid, payment_date) VALUES
  (101, 2024, 8,  'paid',   '2024-08-10'),
  (101, 2024, 9,  'unpaid', '2024-09-15'),
  (101, 2024, 10, 'paid',   '2024-10-05'),
  (101, 2024, 11, 'paid',   '2024-11-20'),
  (101, 2024, 12, 'unpaid', '2024-12-01'),
  (101, 2025, 1,  'paid',   '2025-01-08'),
  (101, 2025, 2,  'unpaid', '2025-02-14'),
  (101, 2025, 3,  'paid',   '2025-03-09'),
  (101, 2025, 4,  'paid',   '2025-04-03'),
  (101, 2025, 5,  'unpaid', '2025-05-11'),
  (101, 2025, 6,  'paid',   '2025-06-22'),
  (101, 2025, 7,  'paid',   '2025-07-02');
