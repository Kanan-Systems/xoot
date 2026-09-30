-- 0003: dashboard writes.
--
-- Runs inside the migrator's BEGIN IMMEDIATE transaction, so it must not
-- issue BEGIN/COMMIT itself.
--
-- event.client gains 'dashboard'. A CHECK cannot be altered in place, so
-- the append-only event table is rebuilt: every row is copied with its id,
-- the AUTOINCREMENT high-water mark is carried over, and the indexes and
-- both append-only triggers are recreated with their 0002 text. The triggers
-- are dropped first so that no rule of theirs runs against the copy.
--
-- confirm_token gains the actor a token was issued to, so an apply must come
-- from the same actor kind and client as its preview. Rows from before this
-- version carry no actor, and a token is only worth something for its five
-- minutes, so the table is recreated empty: pending previews must be taken
-- again.

DROP TRIGGER event_redaction_only;
DROP TRIGGER event_no_delete;
DROP INDEX event_entity;
DROP INDEX event_project;

ALTER TABLE event RENAME TO event_pre_0003;

CREATE TABLE event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project (id),
    entity_type TEXT NOT NULL CHECK (
        entity_type IN ('project', 'workflow', 'item', 'decision')
    ),
    entity_id INTEGER NOT NULL CHECK (entity_id >= 1),
    action TEXT NOT NULL CHECK (
        action IN (
            'create', 'update', 'add_alias', 'add_path', 'remove_alias',
            'remove_path', 'redact'
        )
    ),
    -- 'system' marks changes xoot makes on its own (completion, reopening,
    -- workflow remaps) as a consequence of another actor's write.
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('claude', 'user', 'system')),
    client TEXT NOT NULL CHECK (
        client IN ('chat', 'code', 'paste', 'cli', 'dashboard')
    ),
    before TEXT CHECK (
        before IS NULL OR (json_valid(before) AND json_type(before) = 'object')
    ),
    after TEXT CHECK (
        after IS NULL OR (json_valid(after) AND json_type(after) = 'object')
    ),
    created_at TEXT NOT NULL CHECK (
        created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    -- Set when a redaction rewrote before/after.
    redacted_at TEXT CHECK (
        redacted_at IS NULL
        OR redacted_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    CHECK (before IS NOT NULL OR after IS NOT NULL)
) STRICT;

INSERT INTO event (
    id, project_id, entity_type, entity_id, action, actor_kind, client,
    before, after, created_at, redacted_at
)
SELECT
    id, project_id, entity_type, entity_id, action, actor_kind, client,
    before, after, created_at, redacted_at
FROM event_pre_0003
ORDER BY id;

-- An id is never handed out twice, even one past the highest surviving row.
DELETE FROM sqlite_sequence WHERE name = 'event';
INSERT INTO sqlite_sequence (name, seq)
SELECT 'event', seq FROM sqlite_sequence WHERE name = 'event_pre_0003';

DROP TABLE event_pre_0003;

CREATE INDEX event_entity ON event (entity_type, entity_id, id);
CREATE INDEX event_project ON event (project_id, id);

-- The event log is append-only. The one permitted UPDATE is a redaction:
-- it may rewrite before and after, must stamp redacted_at, and leaves every
-- other column as recorded. DELETE is always refused.
CREATE TRIGGER event_redaction_only BEFORE UPDATE ON event
WHEN NEW.redacted_at IS NULL
    OR NEW.id IS NOT OLD.id
    OR NEW.project_id IS NOT OLD.project_id
    OR NEW.entity_type IS NOT OLD.entity_type
    OR NEW.entity_id IS NOT OLD.entity_id
    OR NEW.action IS NOT OLD.action
    OR NEW.actor_kind IS NOT OLD.actor_kind
    OR NEW.client IS NOT OLD.client
    OR NEW.created_at IS NOT OLD.created_at
BEGIN
    SELECT RAISE(ABORT, 'event is append-only; only a redaction may rewrite it');
END;

CREATE TRIGGER event_no_delete BEFORE DELETE ON event
BEGIN
    SELECT RAISE(ABORT, 'event is append-only');
END;

DROP TABLE confirm_token;

-- Single-use tokens for two-phase writes. Only the token's SHA-256 is
-- stored: the token itself exists only in the preview result, so reading the
-- database is not enough to apply a pending change. A token is bound to one
-- project, one tool, one argument digest, one plan digest and the actor kind
-- and client that previewed, and used_at is set in the same transaction as
-- the write it allows.
CREATE TABLE confirm_token (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_sha256 TEXT NOT NULL UNIQUE CHECK (
        length(token_sha256) = 64 AND token_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    project_id INTEGER NOT NULL REFERENCES project (id),
    tool TEXT NOT NULL CHECK (
        length(tool) BETWEEN 1 AND 64
        AND tool GLOB '[a-z]*'
        AND tool NOT GLOB '*[^a-z_]*'
    ),
    args_sha256 TEXT NOT NULL CHECK (
        length(args_sha256) = 64 AND args_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    -- Digest of the previewed plan: the full post-apply row of every item it
    -- touches (key, kind, title, body digest, state, parent, awaiting
    -- decision). The apply recomputes it under the write lock and refuses a
    -- plan that would leave any of those rows different.
    plan_sha256 TEXT NOT NULL CHECK (
        length(plan_sha256) = 64 AND plan_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('claude', 'user')),
    client TEXT NOT NULL CHECK (
        client IN ('chat', 'code', 'paste', 'cli', 'dashboard')
    ),
    expires_at TEXT NOT NULL CHECK (
        expires_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    -- Fixed-width timestamps compare as text, so a token can never be
    -- recorded as used after it expired.
    used_at TEXT CHECK (
        used_at IS NULL
        OR (
            used_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
            AND used_at < expires_at
        )
    )
) STRICT;
