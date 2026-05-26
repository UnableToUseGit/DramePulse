from __future__ import annotations

import unittest

from services.api.scripts import init_db


class FakeCursor:
    def __init__(self, *, columns: set[str], indexes: set[str]) -> None:
        self.columns = columns
        self.indexes = indexes
        self.executed: list[str] = []
        self._rows: list[dict[str, str]] = []

    def execute(self, sql: str) -> None:
        self.executed.append(sql)
        if sql == "SHOW COLUMNS FROM videos":
            self._rows = [{"Field": column} for column in sorted(self.columns)]
        elif sql == "SHOW INDEX FROM videos":
            self._rows = [{"Key_name": index} for index in sorted(self.indexes)]
        else:
            self._rows = []

    def fetchall(self) -> list[dict[str, str]]:
        return self._rows


class InitDbMigrationTest(unittest.TestCase):
    def test_migrate_videos_table_adds_missing_columns_and_indexes(self) -> None:
        cursor = FakeCursor(
            columns={
                "video_id",
                "title",
                "episode_no",
                "oss_bucket",
                "oss_object_key",
                "content_type",
                "size",
                "source",
                "status",
            },
            indexes={"PRIMARY"},
        )

        init_db.migrate_videos_table(cursor)

        alter_sql = "\n".join(cursor.executed)
        self.assertIn("ALTER TABLE videos ADD COLUMN series_id VARCHAR(128) NULL", alter_sql)
        self.assertIn("ALTER TABLE videos ADD COLUMN duration DOUBLE NULL", alter_sql)
        self.assertIn("ALTER TABLE videos ADD COLUMN updated_at DATETIME(6)", alter_sql)
        self.assertIn("CREATE UNIQUE INDEX uk_videos_oss_object ON videos", alter_sql)
        self.assertIn("CREATE INDEX idx_videos_series_episode ON videos", alter_sql)

    def test_migrate_videos_table_skips_existing_columns_and_indexes(self) -> None:
        cursor = FakeCursor(
            columns=set(init_db.VIDEO_COLUMNS_MYSQL) | {
                "video_id",
                "title",
                "episode_no",
                "oss_bucket",
                "oss_object_key",
                "content_type",
                "size",
                "source",
                "status",
            },
            indexes=set(init_db.VIDEO_INDEXES_MYSQL) | {"PRIMARY"},
        )

        init_db.migrate_videos_table(cursor)

        mutating_sql = [
            sql for sql in cursor.executed if sql.startswith("ALTER TABLE") or sql.startswith("CREATE ")
        ]
        self.assertEqual(mutating_sql, [])


if __name__ == "__main__":
    unittest.main()
