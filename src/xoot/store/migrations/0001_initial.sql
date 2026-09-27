-- 0001: initial schema.
--
-- Runs inside the migrator's BEGIN IMMEDIATE transaction, so it must not
-- issue BEGIN/COMMIT itself. Every table is STRICT. Timestamps are UTC
-- ISO-8601 TEXT in one fixed width (YYYY-MM-DDTHH:MM:SS.ffffffZ). They are
-- for display only: the wall clock can step backwards, so ordering that
-- rules depend on comes from the per-project sequence counter (next_seq).
-- JSON is TEXT checked with json_valid.
--
-- Same-project references use composite foreign keys onto (project_id, id)
-- so a row can never point at another project's row, even if a service
-- check were missed.

CREATE TABLE project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_prefix TEXT NOT NULL UNIQUE CHECK (
        length(key_prefix) BETWEEN 2 AND 32
        AND key_prefix GLOB '[a-z]*'
        AND key_prefix NOT GLOB '*[^a-z0-9-]*'
    ),
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    next_item_number INTEGER NOT NULL DEFAULT 1 CHECK (next_item_number >= 1),
    next_decision_number INTEGER NOT NULL DEFAULT 1
        CHECK (next_decision_number >= 1),
    -- Orders session starts and closes within the project.
    next_seq INTEGER NOT NULL DEFAULT 1 CHECK (next_seq >= 1),
    -- NULL only between the project insert and its first workflow insert,
    -- both inside the registration transaction.
    active_workflow_id INTEGER,
    created_at TEXT NOT NULL CHECK (
        created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    FOREIGN KEY (id, active_workflow_id) REFERENCES workflow (project_id, id)
) STRICT;

CREATE TABLE project_alias (
    alias TEXT NOT NULL PRIMARY KEY CHECK (
        length(alias) BETWEEN 2 AND 32
        AND alias GLOB '[a-z]*'
        AND alias NOT GLOB '*[^a-z0-9-]*'
    ),
    project_id INTEGER NOT NULL REFERENCES project (id)
) STRICT;

CREATE INDEX project_alias_project ON project_alias (project_id);

CREATE TABLE project_path (
    path TEXT NOT NULL PRIMARY KEY CHECK (
        length(path) BETWEEN 1 AND 4096
        AND (
            path = '/'
            OR (
                path GLOB '/*'
                AND path NOT GLOB '*/'
                AND path NOT GLOB '*//*'
                AND path NOT GLOB '*/./*'
                AND path NOT GLOB '*/../*'
                AND path NOT GLOB '*/.'
                AND path NOT GLOB '*/..'
            )
        )
    ),
    project_id INTEGER NOT NULL REFERENCES project (id)
) STRICT;

CREATE INDEX project_path_project ON project_path (project_id);

CREATE TABLE workflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project (id),
    version INTEGER NOT NULL CHECK (version >= 1),
    definition TEXT NOT NULL CHECK (
        json_valid(definition) AND json_type(definition) = 'object'
    ),
    created_at TEXT NOT NULL CHECK (
        created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    UNIQUE (project_id, version),
    UNIQUE (project_id, id)
) STRICT;

CREATE TABLE session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project (id),
    number INTEGER NOT NULL CHECK (number >= 1),
    client TEXT NOT NULL CHECK (client IN ('chat', 'code', 'paste', 'cli')),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    summary TEXT CHECK (summary IS NULL OR length(summary) <= 32768),
    -- Taken from project.next_seq when the session starts and closes.
    start_seq INTEGER NOT NULL CHECK (start_seq >= 1),
    close_seq INTEGER,
    started_at TEXT NOT NULL CHECK (
        started_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    closed_at TEXT CHECK (
        closed_at IS NULL
        OR closed_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    CHECK ((status = 'open') = (closed_at IS NULL)),
    CHECK ((status = 'open') = (close_seq IS NULL)),
    CHECK (close_seq IS NULL OR close_seq > start_seq),
    UNIQUE (project_id, number),
    UNIQUE (project_id, id)
) STRICT;

CREATE TABLE decision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project (id),
    number INTEGER NOT NULL CHECK (number >= 1),
    key TEXT NOT NULL UNIQUE CHECK (key GLOB '*-D' || number),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    body TEXT NOT NULL CHECK (length(body) <= 32768),
    status TEXT NOT NULL CHECK (status IN ('locked', 'deferred', 'superseded')),
    supersedes_id INTEGER CHECK (supersedes_id IS NULL OR supersedes_id <> id),
    scope_item_id INTEGER,
    version INTEGER NOT NULL CHECK (version >= 1),
    created_at TEXT NOT NULL CHECK (
        created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    updated_at TEXT NOT NULL CHECK (
        updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    UNIQUE (project_id, number),
    UNIQUE (project_id, id),
    FOREIGN KEY (project_id, supersedes_id) REFERENCES decision (project_id, id),
    FOREIGN KEY (project_id, scope_item_id) REFERENCES item (project_id, id)
) STRICT;

CREATE TABLE item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project (id),
    number INTEGER NOT NULL CHECK (number >= 1),
    key TEXT NOT NULL UNIQUE CHECK (key GLOB '*-' || number),
    kind TEXT NOT NULL CHECK (kind IN ('goal', 'batch', 'subtask')),
    parent_id INTEGER CHECK (parent_id IS NULL OR parent_id <> id),
    -- The kind a parent must have. Part of the parent foreign key below, so
    -- the database itself rejects a batch under a batch or a subtask under a
    -- goal. Subtasks with no parent ("unfiled") skip the check via NULL.
    parent_kind TEXT GENERATED ALWAYS AS (
        CASE kind WHEN 'batch' THEN 'goal' WHEN 'subtask' THEN 'batch' END
    ) VIRTUAL,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    body TEXT NOT NULL CHECK (length(body) <= 32768),
    state TEXT NOT NULL CHECK (length(state) BETWEEN 1 AND 32),
    backlog_session_id INTEGER,
    awaiting_decision_id INTEGER,
    version INTEGER NOT NULL CHECK (version >= 1),
    created_at TEXT NOT NULL CHECK (
        created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    updated_at TEXT NOT NULL CHECK (
        updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    CHECK (kind <> 'goal' OR parent_id IS NULL),
    CHECK (kind <> 'batch' OR parent_id IS NOT NULL),
    UNIQUE (project_id, number),
    UNIQUE (project_id, id),
    UNIQUE (project_id, id, kind),
    FOREIGN KEY (project_id, parent_id, parent_kind)
        REFERENCES item (project_id, id, kind),
    FOREIGN KEY (project_id, backlog_session_id)
        REFERENCES session (project_id, id),
    FOREIGN KEY (project_id, awaiting_decision_id)
        REFERENCES decision (project_id, id)
) STRICT;

CREATE INDEX item_parent ON item (project_id, parent_id);
CREATE INDEX item_backlog_session ON item (project_id, backlog_session_id);

-- project_id is carried here only so both foreign keys can pin the session
-- and the item to the same project.
CREATE TABLE session_item_ref (
    session_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL REFERENCES project (id),
    linked_at TEXT NOT NULL CHECK (
        linked_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    disposition TEXT CHECK (
        disposition IS NULL
        OR disposition IN (
            'carry_over', 'session_backlog', 'project_backlog', 'dropped'
        )
    ),
    UNIQUE (session_id, item_id),
    FOREIGN KEY (project_id, session_id) REFERENCES session (project_id, id),
    FOREIGN KEY (project_id, item_id) REFERENCES item (project_id, id)
) STRICT;

CREATE INDEX session_item_ref_item ON session_item_ref (item_id);

CREATE TABLE event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project (id),
    entity_type TEXT NOT NULL CHECK (
        entity_type IN ('project', 'workflow', 'item', 'session', 'decision')
    ),
    entity_id INTEGER NOT NULL CHECK (entity_id >= 1),
    action TEXT NOT NULL CHECK (
        action IN (
            'create', 'update', 'link', 'dispose', 'close',
            'add_alias', 'add_path', 'redact'
        )
    ),
    -- 'system' marks changes xoot makes on its own (stale backlog moves,
    -- workflow remaps) as a consequence of another actor's write.
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('claude', 'user', 'system')),
    client TEXT NOT NULL CHECK (client IN ('chat', 'code', 'paste', 'cli')),
    session_id INTEGER,
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
    CHECK (before IS NOT NULL OR after IS NOT NULL),
    FOREIGN KEY (project_id, session_id) REFERENCES session (project_id, id)
) STRICT;

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
    OR NEW.session_id IS NOT OLD.session_id
    OR NEW.created_at IS NOT OLD.created_at
BEGIN
    SELECT RAISE(ABORT, 'event is append-only; only a redaction may rewrite it');
END;

CREATE TRIGGER event_no_delete BEFORE DELETE ON event
BEGIN
    SELECT RAISE(ABORT, 'event is append-only');
END;

-- Single-use tokens for two-phase tool calls. Only the token's SHA-256 is
-- stored: the token itself exists only in the preview result, so reading the
-- database is not enough to apply a pending change. A token is bound to one
-- tool, one argument digest and one session, and used_at is set in the same
-- transaction as the write it allows.
CREATE TABLE confirm_token (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_sha256 TEXT NOT NULL UNIQUE CHECK (
        length(token_sha256) = 64 AND token_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    tool TEXT NOT NULL CHECK (
        length(tool) BETWEEN 1 AND 64
        AND tool GLOB '[a-z]*'
        AND tool NOT GLOB '*[^a-z_]*'
    ),
    args_sha256 TEXT NOT NULL CHECK (
        length(args_sha256) = 64 AND args_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    session_id INTEGER NOT NULL REFERENCES session (id),
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
