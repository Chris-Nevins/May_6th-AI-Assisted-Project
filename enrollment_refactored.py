"""
Module 8 Student Enrollment backend refactor.

This version keeps the same backend idea as the procedural starter, but organizes
the code into clearer layers:

- EnrollmentDatabase: SQLite connection, table creation, raw queries, inserts,
  and updates.
- EnrollmentService: business rules, enrollment-key handling, dashboard meaning,
  soft-unenrollment meaning, and summary counts.
- SnapshotExporter: JSON snapshot creation and file writing.
- main(): small terminal runner for checking behavior.

Out of scope:
    - Streamlit UI
    - authentication/session state
    - caching
    - export formatting beyond the original JSON snapshot
    - production health checks

Run with:
    python enrollment_refactored.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional


DB_PATH = Path(__file__).with_name("student_enrollment_practice.db")
SNAPSHOT_PATH = Path(__file__).with_name("student_enrollment_snapshot.json")

CURRENT_STUDENT = {
    "user_id": "u100",
    "name": "Maya Patel",
    "email": "maya.patel@example.edu",
}

STATUS_ENROLLED = "enrolled"
STATUS_UNENROLLED = "unenrolled"

AVAILABLE_COURSE_KEYS = [
    {
        "course_id": "MISY350",
        "course_name": "Python for Business Analytics",
        "instructor": "Dr. Rivera",
        "enrollment_key": "MISY350-SPRING",
    },
    {
        "course_id": "DATA210",
        "course_name": "Data Storytelling",
        "instructor": "Prof. Morgan",
        "enrollment_key": "DATA210-SPRING",
    },
    {
        "course_id": "WEB220",
        "course_name": "Web Apps With Streamlit",
        "instructor": "Dr. Chen",
        "enrollment_key": "WEB220-SPRING",
    },
]

SAMPLE_ENROLLMENTS = [
    ("u100", "maya.patel@example.edu", "MISY350", STATUS_ENROLLED),
    ("u100", "maya.patel@example.edu", "DATA210", STATUS_UNENROLLED),
    ("u101", "alex@example.edu", "MISY350", STATUS_ENROLLED),
    ("u102", "blair@example.edu", "WEB220", STATUS_ENROLLED),
]


class EnrollmentDatabase:
    """Database layer for student enrollment storage.

    This class owns SQLite connection handling, schema creation, raw queries,
    inserts, and updates. It should avoid deciding what enrollment behavior
    means from a business perspective.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        """Open a database connection."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        """Convert SQLite rows into dictionaries."""
        return [dict(row) for row in rows]

    def create_tables(self) -> None:
        """Create the courses and enrollments tables."""
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS courses (
                    course_id TEXT PRIMARY KEY,
                    course_name TEXT NOT NULL,
                    instructor TEXT NOT NULL,
                    enrollment_key TEXT NOT NULL UNIQUE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS enrollments (
                    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'enrolled',
                    enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, course_id),
                    FOREIGN KEY(course_id) REFERENCES courses(course_id)
                )
                """
            )

    def seed_sample_data(
        self,
        courses: list[dict[str, Any]] = AVAILABLE_COURSE_KEYS,
        enrollments: list[tuple[str, str, str, str]] = SAMPLE_ENROLLMENTS,
    ) -> None:
        """Seed courses, enrollment keys, and practice enrollment records."""
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO courses (
                    course_id, course_name, instructor, enrollment_key
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        course["course_id"],
                        course["course_name"],
                        course["instructor"],
                        course["enrollment_key"],
                    )
                    for course in courses
                ],
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO enrollments (
                    user_id, email, course_id, status
                )
                VALUES (?, ?, ?, ?)
                """,
                enrollments,
            )

    def list_available_course_keys(self) -> list[dict[str, Any]]:
        """Return all available course keys."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT course_id, course_name, instructor, enrollment_key
                FROM courses
                ORDER BY course_id
                """
            ).fetchall()

        return self.rows_to_dicts(rows)

    def find_course_by_key(self, normalized_enrollment_key: str) -> Optional[dict[str, Any]]:
        """Find a course by an already-normalized enrollment key."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT course_id, course_name, instructor, enrollment_key
                FROM courses
                WHERE enrollment_key = ?
                """,
                (normalized_enrollment_key,),
            ).fetchone()

        return dict(row) if row else None

    def list_student_enrollment_records(self, user_id: str) -> list[dict[str, Any]]:
        """Return all enrollment records for one student."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    e.enrollment_id,
                    e.user_id,
                    e.email,
                    e.course_id,
                    c.course_name,
                    c.instructor,
                    e.status,
                    e.enrolled_at
                FROM enrollments e
                JOIN courses c ON c.course_id = e.course_id
                WHERE e.user_id = ?
                ORDER BY c.course_id
                """,
                (user_id,),
            ).fetchall()

        return self.rows_to_dicts(rows)

    def find_student_course_record(
        self,
        user_id: str,
        course_id: str,
    ) -> Optional[dict[str, Any]]:
        """Return one student's enrollment record for one course."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT enrollment_id, user_id, email, course_id, status, enrolled_at
                FROM enrollments
                WHERE user_id = ? AND course_id = ?
                """,
                (user_id, course_id),
            ).fetchone()

        return dict(row) if row else None

    def upsert_enrollment(
        self,
        user_id: str,
        email: str,
        course_id: str,
        status: str,
    ) -> None:
        """Insert or update an enrollment row."""
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO enrollments (user_id, email, course_id, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, course_id)
                DO UPDATE SET
                    email = excluded.email,
                    status = excluded.status,
                    enrolled_at = CURRENT_TIMESTAMP
                """,
                (user_id, email, course_id, status),
            )

    def update_enrollment_status(
        self,
        user_id: str,
        course_id: str,
        status: str,
    ) -> int:
        """Update the status for one enrollment row and return affected row count."""
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE enrollments
                SET status = ?
                WHERE user_id = ? AND course_id = ?
                """,
                (status, user_id, course_id),
            )

        return cursor.rowcount

    def list_all_enrollment_records(self) -> list[dict[str, Any]]:
        """Return every enrollment record for database inspection/export."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    e.enrollment_id,
                    e.user_id,
                    e.email,
                    e.course_id,
                    c.course_name,
                    c.instructor,
                    e.status,
                    e.enrolled_at
                FROM enrollments e
                JOIN courses c ON c.course_id = e.course_id
                ORDER BY e.user_id, e.course_id
                """
            ).fetchall()

        return self.rows_to_dicts(rows)


class EnrollmentService:
    """Service layer for student enrollment behavior.

    This class owns business meaning: validation, enrollment-key normalization,
    dashboard/current enrollment meaning, soft unenrollment behavior, and summary
    counts. It does not write SQL directly.
    """

    def __init__(self, database: EnrollmentDatabase) -> None:
        self.database = database

    def is_valid_user_id(self, user_id: str) -> bool:
        """Return True when user_id is usable for enrollment behavior."""
        return bool(user_id)

    def is_valid_email(self, email: str) -> bool:
        """Return True when email has the basic expected format."""
        return bool(email) and "@" in email

    def normalize_enrollment_key(self, enrollment_key: str) -> str:
        """Clean enrollment key input before database lookup."""
        return enrollment_key.strip().upper()

    def is_valid_enrollment_key(self, enrollment_key: str) -> bool:
        """Return True when enrollment key input is usable."""
        return bool(enrollment_key and enrollment_key.strip())

    def get_available_course_keys(self) -> list[dict[str, Any]]:
        """Return the course keys that a caller could show for practice."""
        return self.database.list_available_course_keys()

    def get_course_by_key(self, enrollment_key: str) -> Optional[dict[str, Any]]:
        """Find a course using a user-entered enrollment key."""
        if not self.is_valid_enrollment_key(enrollment_key):
            return None

        normalized_key = self.normalize_enrollment_key(enrollment_key)
        return self.database.find_course_by_key(normalized_key)

    def get_student_enrollment_history(self, user_id: str) -> list[dict[str, Any]]:
        """Return all enrollment records for one student, including unenrolled."""
        if not self.is_valid_user_id(user_id):
            return []

        return self.database.list_student_enrollment_records(user_id)

    def get_student_dashboard_enrollments(self, user_id: str) -> list[dict[str, Any]]:
        """Return records that count as currently enrolled for the dashboard."""
        history = self.get_student_enrollment_history(user_id)

        return [
            record
            for record in history
            if record["status"] == STATUS_ENROLLED
        ]

    def get_student_course_record(
        self,
        user_id: str,
        course_id: str,
    ) -> Optional[dict[str, Any]]:
        """Return one student's enrollment record for one course."""
        if not self.is_valid_user_id(user_id) or not course_id:
            return None

        return self.database.find_student_course_record(user_id, course_id)

    def enroll_with_key(
        self,
        user_id: str,
        email: str,
        enrollment_key: str,
    ) -> Optional[dict[str, Any]]:
        """Enroll or reactivate a student using a course enrollment key."""
        if not self.is_valid_user_id(user_id):
            return None

        if not self.is_valid_email(email):
            return None

        course = self.get_course_by_key(enrollment_key)
        if not course:
            return None

        self.database.upsert_enrollment(
            user_id=user_id,
            email=email,
            course_id=course["course_id"],
            status=STATUS_ENROLLED,
        )

        return self.get_student_course_record(user_id, course["course_id"])

    def soft_unenroll_student(self, user_id: str, course_id: str) -> bool:
        """Soft-unenroll one student by changing status instead of deleting."""
        if not self.is_valid_user_id(user_id) or not course_id:
            return False

        affected_rows = self.database.update_enrollment_status(
            user_id=user_id,
            course_id=course_id,
            status=STATUS_UNENROLLED,
        )

        return affected_rows > 0

    def get_student_summary(self, user_id: str) -> dict[str, int]:
        """Return summary counts for one student."""
        summary = {
            "total_records": 0,
            STATUS_ENROLLED: 0,
            STATUS_UNENROLLED: 0,
        }

        for record in self.get_student_enrollment_history(user_id):
            summary["total_records"] += 1
            status = record["status"]

            if status in summary:
                summary[status] += 1

        return summary


class SnapshotExporter:
    """Export layer for writing a database snapshot to JSON."""

    def __init__(
        self,
        service: EnrollmentService,
        database: EnrollmentDatabase,
        snapshot_path: Path = SNAPSHOT_PATH,
    ) -> None:
        self.service = service
        self.database = database
        self.snapshot_path = snapshot_path

    def build_snapshot(self, current_student: dict[str, Any]) -> dict[str, Any]:
        """Build the snapshot data structure."""
        return {
            "current_student": current_student,
            "available_course_keys": self.service.get_available_course_keys(),
            "enrollment_table": self.database.list_all_enrollment_records(),
        }

    def export(self, current_student: dict[str, Any]) -> None:
        """Write seeded database content to JSON so students can inspect it."""
        snapshot = self.build_snapshot(current_student)
        self.snapshot_path.write_text(
            json.dumps(snapshot, indent=2),
            encoding="utf-8",
        )


def main() -> None:
    """Small terminal runner for checking behavior before the UI exists."""
    database = EnrollmentDatabase(DB_PATH)
    service = EnrollmentService(database)
    exporter = SnapshotExporter(service, database, SNAPSHOT_PATH)

    database.create_tables()
    database.seed_sample_data()

    user_id = CURRENT_STUDENT["user_id"]
    email = CURRENT_STUDENT["email"]

    print("Current student:")
    print(CURRENT_STUDENT)

    print("\nAvailable enrollment keys:")
    print(service.get_available_course_keys())

    print("\nInitial enrolled classes:")
    print(service.get_student_dashboard_enrollments(user_id))

    print("\nStudent enters key DATA210-SPRING:")
    print(service.enroll_with_key(user_id, email, "DATA210-SPRING"))

    print("\nUpdated enrolled classes:")
    print(service.get_student_dashboard_enrollments(user_id))

    print("\nStudent summary:")
    print(service.get_student_summary(user_id))

    exporter.export(CURRENT_STUDENT)
    print(f"\nDatabase snapshot written to: {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
