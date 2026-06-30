import aiosqlite
import json


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: aiosqlite.Connection | None = None

    async def init(self):
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS backends (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                api_base TEXT NOT NULL,
                api_key TEXT NOT NULL,
                model_name TEXT NOT NULL,
                rpm INTEGER DEFAULT 120
            );
            CREATE TABLE IF NOT EXISTS model_groups (
                name TEXT PRIMARY KEY,
                fallback TEXT
            );
            CREATE TABLE IF NOT EXISTS model_group_members (
                group_name TEXT NOT NULL,
                model_id TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                PRIMARY KEY (group_name, model_id),
                FOREIGN KEY (group_name) REFERENCES model_groups(name),
                FOREIGN KEY (model_id) REFERENCES backends(id)
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                models TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                group_name TEXT,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_usage_model ON usage_logs(model_id);
            CREATE INDEX IF NOT EXISTS idx_usage_provider ON usage_logs(provider);
            CREATE INDEX IF NOT EXISTS idx_usage_group ON usage_logs(group_name);
        """)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def add_backend(self, id: str, provider: str, api_base: str,
                          api_key: str, model_name: str, rpm: int = 120):
        await self.conn.execute(
            "INSERT OR REPLACE INTO backends VALUES (?, ?, ?, ?, ?, ?)",
            (id, provider, api_base, api_key, model_name, rpm)
        )
        await self.conn.commit()

    async def get_backend(self, id: str) -> dict | None:
        cursor = await self.conn.execute("SELECT * FROM backends WHERE id = ?", (id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_backends(self) -> list[dict]:
        cursor = await self.conn.execute("SELECT * FROM backends")
        return [dict(row) for row in await cursor.fetchall()]

    async def delete_backend(self, id: str):
        await self.conn.execute("DELETE FROM backends WHERE id = ?", (id,))
        await self.conn.commit()

    async def add_group(self, name: str, fallback: str | None = None):
        await self.conn.execute(
            "INSERT OR REPLACE INTO model_groups VALUES (?, ?)", (name, fallback)
        )
        await self.conn.commit()

    async def get_group(self, name: str) -> dict | None:
        cursor = await self.conn.execute("SELECT * FROM model_groups WHERE name = ?", (name,))
        row = await cursor.fetchone()
        if not row:
            return None
        group = dict(row)
        cursor2 = await self.conn.execute(
            "SELECT model_id, weight FROM model_group_members WHERE group_name = ?", (name,)
        )
        members = await cursor2.fetchall()
        group["members"] = [{"model_id": m["model_id"], "weight": m["weight"]} for m in members]
        return group

    async def list_groups(self) -> list[dict]:
        cursor = await self.conn.execute("SELECT name FROM model_groups")
        names = [row["name"] for row in await cursor.fetchall()]
        groups = []
        for name in names:
            g = await self.get_group(name)
            if g:
                groups.append(g)
        return groups

    async def add_group_member(self, group_name: str, model_id: str, weight: float = 1.0):
        await self.conn.execute(
            "INSERT OR REPLACE INTO model_group_members VALUES (?, ?, ?)",
            (group_name, model_id, weight)
        )
        await self.conn.commit()

    async def delete_group(self, name: str):
        await self.conn.execute("DELETE FROM model_group_members WHERE group_name = ?", (name,))
        await self.conn.execute("DELETE FROM model_groups WHERE name = ?", (name,))
        await self.conn.commit()

    async def add_api_key(self, key_hash: str, name: str, models: str | None = None):
        await self.conn.execute(
            "INSERT OR REPLACE INTO api_keys (key_hash, name, models) VALUES (?, ?, ?)",
            (key_hash, name, models)
        )
        await self.conn.commit()

    async def get_api_key(self, key_hash: str) -> dict | None:
        cursor = await self.conn.execute("SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,))
        row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        if result["models"]:
            result["models"] = json.loads(result["models"])
        return result

    async def list_api_keys(self) -> list[dict]:
        cursor = await self.conn.execute("SELECT * FROM api_keys")
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            r = dict(row)
            if r["models"]:
                r["models"] = json.loads(r["models"])
            result.append(r)
        return result

    async def delete_api_key(self, key_hash: str):
        await self.conn.execute("DELETE FROM api_keys WHERE key_hash = ?", (key_hash,))
        await self.conn.commit()

    async def record_usage(self, model_id: str, provider: str, group_name: str | None,
                           prompt_tokens: int, completion_tokens: int, total_tokens: int):
        await self.conn.execute(
            "INSERT INTO usage_logs (model_id, provider, group_name, prompt_tokens, completion_tokens, total_tokens) VALUES (?, ?, ?, ?, ?, ?)",
            (model_id, provider, group_name, prompt_tokens, completion_tokens, total_tokens)
        )
        await self.conn.commit()

    async def get_usage_stats(self, since: str | None = None, until: str | None = None,
                              group_by: str = "model") -> list[dict]:
        valid_group_by = {"model": "model_id", "provider": "provider", "group": "group_name"}
        col = valid_group_by.get(group_by, "model_id")
        conditions = []
        params = []
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("timestamp <= ?")
            params.append(until)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT {col} as name, COUNT(*) as request_count,
                   SUM(prompt_tokens) as prompt_tokens, SUM(completion_tokens) as completion_tokens,
                   SUM(total_tokens) as total_tokens
            FROM usage_logs {where} GROUP BY {col} ORDER BY total_tokens DESC
        """
        cursor = await self.conn.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]

    async def get_usage_summary(self, since: str | None = None, until: str | None = None) -> dict:
        conditions = []
        params = []
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("timestamp <= ?")
            params.append(until)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT COUNT(*) as total_requests, SUM(prompt_tokens) as total_prompt_tokens,
                   SUM(completion_tokens) as total_completion_tokens, SUM(total_tokens) as total_tokens
            FROM usage_logs {where}
        """
        cursor = await self.conn.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else {}
