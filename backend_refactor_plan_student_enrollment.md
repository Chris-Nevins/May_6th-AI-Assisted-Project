# Backend Refactor Plan: Student Enrollment System

## Goal

Move the current procedural student enrollment backend toward an **object-oriented, layered design**.

The main goal is **not** to change what the program does yet. The goal is to organize responsibilities more clearly so the project is easier to extend, test, and maintain.

---

# 1. Current Design Problem

The current file works, but it is overloaded.

It currently handles:

| Responsibility | Currently in Same File? | Problem |
|---|---:|---|
| SQLite connection | Yes | Database access is mixed with service logic |
| Table creation | Yes | Setup logic is mixed with application behavior |
| Seed/sample data | Yes | Practice/demo data is mixed with backend logic |
| Enrollment key lookup | Yes | SQL and business validation are combined |
| Student enrollment behavior | Yes | Service decisions are buried inside SQL-heavy functions |
| Student dashboard meaning | Yes | “Current enrollments” is defined directly inside SQL |
| Soft unenrollment | Yes | Business action and database update happen in one method |
| Summary counts | Yes | Business reporting depends directly on database-shaped dictionaries |
| JSON snapshot export | Yes | Export logic mixes database reads and file writing |
| Main test/demo runner | Yes | Running the file mutates the database and writes files |

---

# 2. Target Layered Design

The backend should be separated into clearer layers.

## Recommended Layers

| Layer | Responsibility | Should Contain SQL? | Should Contain Business Meaning? |
|---|---|---:|---:|
| Database Layer | SQLite connection, table creation, raw queries, inserts, updates | Yes | No, or very little |
| Service Layer | Enrollment rules, validation, dashboard meaning, summaries | No direct SQL | Yes |
| Export Layer | JSON snapshot writing | No direct SQL if possible | Minimal |
| Runner / Demo Layer | Calls setup and demonstrates behavior | No direct SQL | Minimal |

---

# 3. Suggested Class Structure

## A. `EnrollmentDatabase`

This class should focus on SQLite operations only.

### Main responsibility

Talk to SQLite and return raw records.

### It should handle:

| Method Area | Responsibility |
|---|---|
| Connect to SQLite | Open database connection |
| Create tables | Create `courses` and `enrollments` tables |
| Seed data | Insert practice courses and enrollments |
| Course queries | Find courses by key or list courses |
| Enrollment queries | Find enrollment records |
| Enrollment writes | Insert, update, or soft-unenroll records |

### It should avoid:

| Avoid | Reason |
|---|---|
| Deciding what a dashboard means | That is service logic |
| Deciding whether an enrollment key is valid from a user perspective | That is service logic |
| Deciding whether an action should be called “reactivation” | That is service logic |
| Writing JSON snapshots | That is export logic |
| Referring to `CURRENT_STUDENT` | That is demo/application state |

---

## B. `EnrollmentService`

This class should hold the business meaning.

### Main responsibility

Decide what student enrollment actions mean.

### It should handle:

| Method Area | Responsibility |
|---|---|
| Enrollment key validation | Clean, normalize, and validate the key |
| Course joining | Decide whether a student can enroll |
| Reactivation logic | Decide what happens when a student was previously unenrolled |
| Current dashboard classes | Decide that only `status == "enrolled"` appears on dashboard |
| Enrollment history | Return full history when needed |
| Soft unenrollment meaning | Decide what it means to unenroll without deleting |
| Student summary | Count total, enrolled, and unenrolled records |

### It should avoid:

| Avoid | Reason |
|---|---|
| Writing SQL directly | That belongs in the database layer |
| Opening SQLite connections directly | That belongs in the database layer |
| Writing JSON files | That belongs in the export layer |
| Hardcoding demo-only student behavior | That belongs in the runner/demo setup |

---

## C. `SnapshotExporter`

This class or small function should handle export behavior.

### Main responsibility

Create a JSON snapshot from service/database results.

### It should handle:

| Responsibility | Notes |
|---|---|
| Build snapshot dictionary | Use service/database methods to gather data |
| Write JSON file | Save snapshot to `SNAPSHOT_PATH` |
| Keep export formatting separate | Avoid mixing export concerns into enrollment behavior |

### It should avoid:

| Avoid | Reason |
|---|---|
| Making enrollment decisions | That belongs in the service layer |
| Running SQL directly | That belongs in the database layer |
| Owning student identity | It should receive the student or data from the caller |

---

## D. `main()`

The `main()` function should only be a small demo runner.

### Main responsibility

Show that the backend still works.

### It should handle:

| Responsibility | Notes |
|---|---|
| Create database object | Example: database layer instance |
| Create service object | Service receives database object |
| Create tables | Setup only |
| Seed data | Demo only |
| Run sample enrollment flow | For checking behavior |
| Export snapshot | Optional demo step |

### It should avoid:

| Avoid | Reason |
|---|---|
| Containing business logic | Business logic belongs in the service |
| Containing SQL | SQL belongs in the database class |
| Becoming a UI replacement | The assignment says UI is out of scope |

---

# 4. What Should Move Where?

## Current Function Mapping

| Current Item | Current Problem | Future Location | Reason |
|---|---|---|---|
| `DB_PATH` | Global config used everywhere | Database setup/config area | It belongs near database construction |
| `SNAPSHOT_PATH` | Global export config | Export setup/config area | It belongs near snapshot writing |
| `CURRENT_STUDENT` | Demo/application state | Demo runner or sample config | It should not drive backend design |
| `STATUS_ENROLLED` | Business constant | Service constants or shared constants | The service owns status meaning |
| `STATUS_UNENROLLED` | Business constant | Service constants or shared constants | The service owns status meaning |
| `AVAILABLE_COURSE_KEYS` | Seed data | Seed/demo setup | It is not core service logic |
| `SAMPLE_ENROLLMENTS` | Seed data | Seed/demo setup | It is not core service logic |
| `connect()` | SQLite connection | `EnrollmentDatabase` | Pure database responsibility |
| `create_tables()` | SQLite schema setup | `EnrollmentDatabase` | Pure database responsibility |
| `seed_sample_data()` | Inserts sample data | `EnrollmentDatabase` or setup helper | Database insert behavior, but sample data itself is demo/setup |
| `rows_to_dicts()` | SQLite helper | `EnrollmentDatabase` helper | Converts database rows |
| `get_available_course_keys()` | SQL read | `EnrollmentDatabase` | Mostly database/repository behavior |
| `get_course_by_key()` | SQL read plus key cleanup | Split between service and database | Service cleans key; database queries by cleaned key |
| `get_student_enrollments()` | SQL read plus dashboard meaning | Split between service and database | Database fetches records; service decides active/dashboard records |
| `get_student_enrollment_history()` | SQL read | `EnrollmentDatabase` | Mostly database/repository behavior |
| `get_student_course_record()` | SQL read | `EnrollmentDatabase` | Raw database lookup |
| `enroll_with_key()` | Too many jobs | `EnrollmentService` with database helper methods | Service owns enrollment meaning; database performs writes |
| `soft_unenroll_student()` | Business action plus SQL update | Split between service and database | Service decides action; database updates row |
| `get_student_summary()` | Business aggregation | `EnrollmentService` | Summary is business/reporting meaning |
| `get_all_enrollment_records()` | SQL read | `EnrollmentDatabase` | Raw database query |
| `export_database_snapshot()` | Export plus data gathering | `SnapshotExporter` | Export concern should be separate |
| `main()` | Demo runner | Keep as small runner | Good for testing behavior, but not core logic |

---

# 5. Where Database Code Is Making Service-Level Decisions

This is the most important issue to fix.

| Current Method | Database Work | Service-Level Decision Hidden Inside |
|---|---|---|
| `get_course_by_key()` | Queries course by enrollment key | Cleans and uppercases the key |
| `get_student_enrollments()` | Queries enrollments | Decides dashboard only means `status = enrolled` |
| `enroll_with_key()` | Inserts or updates enrollment row | Decides valid email, valid key, reactivation, enrolled status, and return meaning |
| `soft_unenroll_student()` | Updates enrollment status | Decides unenrollment means changing status instead of deleting |
| `get_student_summary()` | Uses enrollment records | Decides how records should be counted and interpreted |

The better design is:

| Concern | Better Owner |
|---|---|
| SQL query | Database layer |
| Input cleanup | Service layer |
| Enrollment key validation | Service layer |
| Active enrollment meaning | Service layer |
| Reactivation rule | Service layer |
| Soft unenrollment meaning | Service layer |
| Summary counts | Service layer |
| JSON file writing | Export layer |

---

# 6. What Should Be Discarded, Simplified, or Revamped?

## Should Be Kept

| Item | Why Keep It |
|---|---|
| SQLite database | It matches the assignment focus |
| `courses` table | Good core table |
| `enrollments` table | Good core table |
| `status = enrolled/unenrolled` idea | Good example of soft unenrollment |
| Enrollment keys | Central to the app idea |
| Sample data | Useful for practice/testing |
| JSON snapshot | Useful for inspecting seeded data |
| `main()` runner | Useful for checking behavior before UI exists |

---

## Should Be Simplified

| Item | How to Simplify |
|---|---|
| `main()` | Keep it as a short demo only |
| Seed data | Keep it separate from core business behavior |
| Snapshot export | Move it away from enrollment logic |
| Summary logic | Keep it in service layer, not mixed with database code |
| Key cleanup | Make it a clear service step before database lookup |

---

## Should Be Revamped

| Item | Why Revamp It |
|---|---|
| `enroll_with_key()` | It currently does too many jobs |
| `get_student_enrollments()` | It mixes SQL with dashboard meaning |
| `get_course_by_key()` | It mixes key normalization with database lookup |
| `soft_unenroll_student()` | It mixes business meaning with database update |
| SQL organization | SQL is currently dispersed throughout the backend |
| File-level responsibilities | The file has too many unrelated jobs |

---

## Should Not Be Discarded Completely

Nothing major needs to be completely discarded.

The better approach is to **move responsibilities**, not delete the project.

In plain English:

> The current code should not be thrown away. Most of the logic is useful, but it is sitting in the wrong places. The refactor should preserve behavior while moving SQL into a database class and business meaning into a service class.

---

# 7. Recommended Refactor Approach

## Best Approach: Gradual Layered Refactor

Do not rewrite everything at once.

Use this order:

| Step | Goal | Why This Order Works |
|---|---|---|
| 1 | Create `EnrollmentDatabase` | Move SQLite details into one place first |
| 2 | Move connection, table creation, seed, and raw queries into database class | This removes scattered SQL |
| 3 | Create `EnrollmentService` | Give business rules a clear home |
| 4 | Move enrollment-key validation into service | Keeps user/action meaning out of SQL methods |
| 5 | Move dashboard meaning into service | Service decides which records count as current dashboard classes |
| 6 | Move summary logic into service | Summary is business/reporting logic |
| 7 | Separate snapshot export | Keeps file writing away from enrollment behavior |
| 8 | Reduce `main()` to a small runner | Keeps the demo flow but prevents it from becoming core logic |

---

# 8. Ideal Organization of SQL

The simpler method is:

## Database layer should have small query/update methods

Examples of responsibilities, without writing code:

| Database Method Type | What It Should Do |
|---|---|
| Find course by key | Receive an already-cleaned key and return matching course |
| List courses | Return course rows |
| Find enrollment record | Return one student-course record |
| List enrollment records for student | Return all records for a student |
| Insert or update enrollment | Perform the database write |
| Update enrollment status | Change status in the database |
| List all enrollment records | Return records for snapshot |

The database method should not decide:

| Database Should Not Decide | Belongs In |
|---|---|
| Whether the enrollment key is acceptable | Service |
| Whether a student is “currently enrolled” for dashboard purposes | Service |
| Whether a previous unenrollment should count as reactivation | Service |
| Whether returned data should be shown as a dashboard | Service |
| Whether export should include current student | Export/runner |

---

# 9. Target Object-Oriented Design

## Suggested Object Relationships

| Object | Depends On | Purpose |
|---|---|---|
| `EnrollmentDatabase` | SQLite path | Handles database setup and SQL |
| `EnrollmentService` | `EnrollmentDatabase` | Handles enrollment behavior and business rules |
| `SnapshotExporter` | `EnrollmentService` and/or `EnrollmentDatabase` | Writes inspection snapshot |
| `main()` | All objects | Demonstrates the flow |

---

# 10. Planned Method Ownership

## Database Layer Methods

| Future Owner | Method Responsibility |
|---|---|
| `EnrollmentDatabase` | connect to SQLite |
| `EnrollmentDatabase` | create tables |
| `EnrollmentDatabase` | seed sample data |
| `EnrollmentDatabase` | convert rows to dictionaries |
| `EnrollmentDatabase` | list available courses |
| `EnrollmentDatabase` | find course by normalized key |
| `EnrollmentDatabase` | list all records for a student |
| `EnrollmentDatabase` | find one student-course record |
| `EnrollmentDatabase` | insert or reactivate enrollment row |
| `EnrollmentDatabase` | update enrollment status |
| `EnrollmentDatabase` | list all enrollment records |

---

## Service Layer Methods

| Future Owner | Method Responsibility |
|---|---|
| `EnrollmentService` | validate user id |
| `EnrollmentService` | validate email |
| `EnrollmentService` | normalize enrollment key |
| `EnrollmentService` | enroll student with key |
| `EnrollmentService` | soft-unenroll student |
| `EnrollmentService` | get dashboard enrollments |
| `EnrollmentService` | get enrollment history |
| `EnrollmentService` | get student summary |
| `EnrollmentService` | decide what counts as enrolled or unenrolled |

---

## Export Layer Methods

| Future Owner | Method Responsibility |
|---|---|
| `SnapshotExporter` | build snapshot data |
| `SnapshotExporter` | write snapshot JSON |

---

# 11. What AI Should Avoid While Planning

AI should avoid:

| Avoid | Reason |
|---|---|
| Rewriting the UI layer | UI is out of scope |
| Adding Streamlit | The starter says Streamlit UI is out of scope |
| Changing the app idea | The current behavior should be preserved |
| Changing the database schema unnecessarily | Refactor structure first, not features |
| Adding authentication/session state | Explicitly out of scope |
| Adding caching | Explicitly out of scope |
| Adding production health checks | Explicitly out of scope |
| Overengineering with too many classes | The goal is clearer layers, not complexity |
| Turning every small helper into a class | That would make the refactor harder to understand |
| Removing SQLite | SQLite is part of the assignment focus |
| Removing the JSON snapshot | It is useful for inspecting seeded data |
| Changing behavior before organizing responsibilities | First refactor structure, then improve behavior later |
| Writing code before the plan is approved | This step is only planning |

---

# 12. Best Plain-English Explanation

The best approach is to **keep the same backend behavior but move responsibilities into cleaner places**.

Right now, the code works, but many methods have two jobs:

1. They talk to the database.
2. They decide what enrollment behavior means.

That is the core issue.

The database layer should answer simple questions like:

> “What rows match this query?”

The service layer should answer business questions like:

> “Is this a valid enrollment key?”  
> “Should this student be shown as currently enrolled?”  
> “Does this action reactivate a previous enrollment?”  
> “What should the dashboard summary mean?”

That separation makes the project easier to maintain because SQL changes stay in one place, and enrollment rules stay in another place.

---

# 13. Implementation Prompt to Use After Approval

Use this prompt after you approve the plan:

```text
Refactor the provided Module 8 Student Enrollment backend starter from procedural code into an object-oriented, layered backend design.

Important constraints:
- Do not create or rewrite any UI layer.
- Do not add Streamlit.
- Do not add authentication, session state, caching, or production health checks.
- Preserve the current behavior as much as possible.
- Keep SQLite as the database.
- Keep the JSON snapshot feature.
- Do not unnecessarily change the database schema.
- Focus on structure and responsibility separation.

Refactor goals:
1. Create an EnrollmentDatabase class.
   - It should own SQLite connection handling.
   - It should create tables.
   - It should seed sample data.
   - It should contain raw SQLite SELECT, INSERT, and UPDATE operations.
   - It should return dictionaries/lists of dictionaries.
   - It should avoid business meaning where possible.

2. Create an EnrollmentService class.
   - It should own business rules and enrollment meaning.
   - It should validate user_id, email, and enrollment keys.
   - It should normalize enrollment keys before sending them to the database layer.
   - It should decide what counts as a dashboard/current enrollment.
   - It should handle enroll-with-key behavior.
   - It should handle soft unenrollment behavior.
   - It should calculate student summary counts.
   - It should avoid writing SQL directly.

3. Separate snapshot export behavior.
   - Move JSON snapshot writing into a small SnapshotExporter class or clearly separated function.
   - It should gather the current student, available course keys, and enrollment records.
   - It should write the same kind of JSON snapshot as before.

4. Keep main() only as a small terminal runner.
   - It should create the database object.
   - It should create the service object.
   - It should create tables and seed sample data.
   - It should demonstrate the same basic flow as the original file.
   - It should export the snapshot.

Specific design expectations:
- SQL should be concentrated in the database layer.
- Business decisions should be concentrated in the service layer.
- The service layer may call database methods, but the database layer should not call service methods.
- Enrollment-key validation and normalization should be service-layer responsibilities.
- Dashboard meaning should be service-layer responsibility.
- The database should focus on row queries and row updates.

Before giving the final refactored code, briefly explain:
- what moved to the database layer
- what moved to the service layer
- what moved to the export layer
- what stayed in main()
```

---

# 14. Final Recommendation

Use a **gradual layered refactor**.

Do not discard the current project. Do not completely revamp the behavior. Instead, reorganize it.

The strongest improvement is:

> Put SQLite in `EnrollmentDatabase`, put enrollment meaning in `EnrollmentService`, put JSON writing in a snapshot/export piece, and keep `main()` as a small demo runner.
