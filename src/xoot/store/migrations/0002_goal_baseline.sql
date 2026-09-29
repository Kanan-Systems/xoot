-- 0002: the goal-centric baseline (xoot 0.3).
--
-- There is no 0001 any more: the 0.2 schema (sessions, flat keys) is not
-- migrated, and a database at version 1 is refused before anything runs.
-- A fresh database applies this file and ends at version 2.
--
-- Runs inside the migrator's BEGIN IMMEDIATE transaction, so it must not
-- issue BEGIN/COMMIT itself. Every table is STRICT. Timestamps are UTC
-- ISO-8601 TEXT in one fixed width (YYYY-MM-DDTHH:MM:SS.ffffffZ), for
-- display only. JSON is TEXT checked with json_valid.
--
-- Same-project references use composite foreign keys onto (project_id, id)
-- so a row can never point at another project's row, even if a service
-- check were missed. Where a reference must name one kind of item, the
-- foreign key also covers the kind.

CREATE TABLE project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_prefix TEXT NOT NULL UNIQUE CHECK (
        length(key_prefix) BETWEEN 2 AND 32
        AND key_prefix GLOB '[a-z]*'
        AND key_prefix NOT GLOB '*[^a-z0-9]*'
    ),
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    -- Numbers of the items that sit directly on the project. They only
    -- grow, so a key is never handed out twice, not even after a move.
    next_goal_number INTEGER NOT NULL DEFAULT 1 CHECK (next_goal_number >= 1),
    next_backlog_number INTEGER NOT NULL DEFAULT 1
        CHECK (next_backlog_number >= 1),
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
        -- Not key-shaped: an item or decision kind, a dash and a number.
        AND alias NOT GLOB 'goal-[0-9]*'
        AND alias NOT GLOB 'batch-[0-9]*'
        AND alias NOT GLOB 'subtask-[0-9]*'
        AND alias NOT GLOB 'backlog-[0-9]*'
        AND alias NOT GLOB 'decision-[0-9]*'
    ),
    project_id INTEGER NOT NULL REFERENCES project (id)
) STRICT;

CREATE INDEX project_alias_project ON project_alias (project_id);

-- Prefixes and aliases share one namespace: every name resolves to exactly
-- one project. An alias equal to its own project's prefix is redundant but
-- unambiguous, so it is allowed.
CREATE TRIGGER project_alias_not_other_prefix
BEFORE INSERT ON project_alias
WHEN EXISTS (
    SELECT 1 FROM project WHERE key_prefix = NEW.alias AND id <> NEW.project_id
)
BEGIN
    SELECT RAISE(ABORT, 'alias names another project');
END;

CREATE TRIGGER project_alias_update_not_other_prefix
BEFORE UPDATE OF alias, project_id ON project_alias
WHEN EXISTS (
    SELECT 1 FROM project WHERE key_prefix = NEW.alias AND id <> NEW.project_id
)
BEGIN
    SELECT RAISE(ABORT, 'alias names another project');
END;

CREATE TRIGGER project_prefix_not_other_alias
BEFORE INSERT ON project
WHEN EXISTS (
    SELECT 1 FROM project_alias WHERE alias = NEW.key_prefix
)
BEGIN
    SELECT RAISE(ABORT, 'key prefix names another project');
END;

CREATE TRIGGER project_prefix_update_not_other_alias
BEFORE UPDATE OF key_prefix ON project
WHEN EXISTS (
    SELECT 1 FROM project_alias
    WHERE alias = NEW.key_prefix AND project_id <> NEW.id
)
BEGIN
    SELECT RAISE(ABORT, 'key prefix names another project');
END;

CREATE TABLE project_path (
    -- "/" is refused: it would claim every directory on the machine.
    path TEXT NOT NULL PRIMARY KEY CHECK (
        length(path) BETWEEN 2 AND 4096
        AND path GLOB '/*'
        AND path NOT GLOB '*/'
        AND path NOT GLOB '*//*'
        AND path NOT GLOB '*/./*'
        AND path NOT GLOB '*/../*'
        AND path NOT GLOB '*/.'
        AND path NOT GLOB '*/..'
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

-- Goals sit on the project, batches in a goal, subtasks in a batch, and
-- backlog items in a batch, in a goal, or on the project. key is the
-- nested path of kind-number segments down from the project, e.g.
-- goal-1/batch-2/subtask-3; each number is allocated by the parent (the
-- project for top-level items) from a counter that only grows.
CREATE TABLE item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project (id),
    kind TEXT NOT NULL CHECK (kind IN ('goal', 'batch', 'subtask', 'backlog')),
    number INTEGER NOT NULL CHECK (number >= 1),
    key TEXT NOT NULL CHECK (
        length(key) BETWEEN 6 AND 160
        AND key NOT GLOB '*[^a-z0-9/-]*'
        AND (
            key = kind || '-' || number
            OR key GLOB '*/' || kind || '-' || number
        )
        AND (
            (kind = 'goal' AND key = 'goal-' || number)
            OR (
                kind = 'batch'
                AND key GLOB 'goal-[1-9]*/batch-[1-9]*'
                AND length(key) - length(replace(key, '/', '')) = 1
            )
            OR (
                kind = 'subtask'
                AND key GLOB 'goal-[1-9]*/batch-[1-9]*/subtask-[1-9]*'
                AND length(key) - length(replace(key, '/', '')) = 2
            )
            OR (
                kind = 'backlog'
                AND (
                    key = 'backlog-' || number
                    OR (
                        key GLOB 'goal-[1-9]*/backlog-[1-9]*'
                        AND length(key) - length(replace(key, '/', '')) = 1
                    )
                    OR (
                        key GLOB 'goal-[1-9]*/batch-[1-9]*/backlog-[1-9]*'
                        AND length(key) - length(replace(key, '/', '')) = 2
                    )
                )
            )
        )
    ),
    parent_id INTEGER CHECK (parent_id IS NULL OR parent_id <> id),
    -- The parent's kind, stored so the parent foreign key below can pin it.
    parent_kind TEXT,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    body TEXT NOT NULL CHECK (length(body) <= 32768),
    state TEXT NOT NULL CHECK (length(state) BETWEEN 1 AND 32),
    -- Backlog only: the item the backlog entry was found on.
    found_on_item_id INTEGER,
    -- Backlog only: the subtask it became.
    covered_by_item_id INTEGER,
    covered_by_kind TEXT GENERATED ALWAYS AS (
        CASE WHEN covered_by_item_id IS NOT NULL THEN 'subtask' END
    ) VIRTUAL,
    -- Subtask only: the backlog entry it came from.
    origin_item_id INTEGER,
    origin_kind TEXT GENERATED ALWAYS AS (
        CASE WHEN origin_item_id IS NOT NULL THEN 'backlog' END
    ) VIRTUAL,
    awaiting_decision_id INTEGER,
    -- Counters for what this item numbers: its batches or subtasks, its own
    -- backlog, its decisions. Never part of the item's version.
    next_child_number INTEGER NOT NULL DEFAULT 1 CHECK (next_child_number >= 1),
    next_backlog_number INTEGER NOT NULL DEFAULT 1
        CHECK (next_backlog_number >= 1),
    next_decision_number INTEGER NOT NULL DEFAULT 1
        CHECK (next_decision_number >= 1),
    version INTEGER NOT NULL CHECK (version >= 1),
    created_at TEXT NOT NULL CHECK (
        created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    updated_at TEXT NOT NULL CHECK (
        updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    CHECK ((parent_id IS NULL) = (parent_kind IS NULL)),
    CHECK (
        (kind = 'goal' AND parent_id IS NULL)
        OR (kind = 'batch' AND parent_kind = 'goal')
        OR (kind = 'subtask' AND parent_kind = 'batch')
        OR (
            kind = 'backlog'
            AND (parent_kind IS NULL OR parent_kind IN ('goal', 'batch'))
        )
    ),
    CHECK ((kind = 'backlog') = (found_on_item_id IS NOT NULL)),
    CHECK (kind = 'backlog' OR covered_by_item_id IS NULL),
    CHECK (kind = 'subtask' OR origin_item_id IS NULL),
    UNIQUE (project_id, key),
    UNIQUE (project_id, id),
    UNIQUE (project_id, id, kind),
    FOREIGN KEY (project_id, parent_id, parent_kind)
        REFERENCES item (project_id, id, kind),
    FOREIGN KEY (project_id, found_on_item_id) REFERENCES item (project_id, id),
    FOREIGN KEY (project_id, covered_by_item_id, covered_by_kind)
        REFERENCES item (project_id, id, kind),
    FOREIGN KEY (project_id, origin_item_id, origin_kind)
        REFERENCES item (project_id, id, kind),
    FOREIGN KEY (project_id, awaiting_decision_id)
        REFERENCES decision (project_id, id)
) STRICT;

CREATE INDEX item_parent ON item (project_id, parent_id);
CREATE UNIQUE INDEX item_origin ON item (origin_item_id)
    WHERE origin_item_id IS NOT NULL;
CREATE UNIQUE INDEX item_covered_by ON item (covered_by_item_id)
    WHERE covered_by_item_id IS NOT NULL;

-- A key is always its parent's key, a slash, and its own kind-number
-- segment. Checked on every write of the key or the parent; a move writes
-- the moved item first and then each descendant, top down.
CREATE TRIGGER item_key_matches_parent
BEFORE INSERT ON item
WHEN NEW.key IS NOT (
    CASE
        WHEN NEW.parent_id IS NULL THEN ''
        ELSE (SELECT key FROM item WHERE id = NEW.parent_id) || '/'
    END || NEW.kind || '-' || NEW.number
)
BEGIN
    SELECT RAISE(ABORT, 'item key does not match its parent');
END;

CREATE TRIGGER item_key_update_matches_parent
BEFORE UPDATE OF key, parent_id, number ON item
WHEN NEW.key IS NOT (
    CASE
        WHEN NEW.parent_id IS NULL THEN ''
        ELSE (SELECT key FROM item WHERE id = NEW.parent_id) || '/'
    END || NEW.kind || '-' || NEW.number
)
BEGIN
    SELECT RAISE(ABORT, 'item key does not match its parent');
END;

CREATE TRIGGER item_kind_fixed
BEFORE UPDATE OF kind, project_id ON item
WHEN NEW.kind IS NOT OLD.kind OR NEW.project_id IS NOT OLD.project_id
BEGIN
    SELECT RAISE(ABORT, 'an item never changes kind or project');
END;

-- Every key an item held before a move. Keys are never handed out twice,
-- so an old key names exactly one item forever.
CREATE TABLE item_alias (
    project_id INTEGER NOT NULL REFERENCES project (id),
    alias_key TEXT NOT NULL CHECK (
        length(alias_key) BETWEEN 6 AND 160
        AND alias_key NOT GLOB '*[^a-z0-9/-]*'
    ),
    item_id INTEGER NOT NULL,
    created_at TEXT NOT NULL CHECK (
        created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    PRIMARY KEY (project_id, alias_key),
    FOREIGN KEY (project_id, item_id) REFERENCES item (project_id, id)
) STRICT;

CREATE INDEX item_alias_item ON item_alias (item_id);

CREATE TRIGGER item_alias_not_live
BEFORE INSERT ON item_alias
WHEN EXISTS (
    SELECT 1 FROM item
    WHERE project_id = NEW.project_id AND key = NEW.alias_key
)
BEGIN
    SELECT RAISE(ABORT, 'an alias cannot name a live key');
END;

CREATE TRIGGER item_key_not_alias
BEFORE INSERT ON item
WHEN EXISTS (
    SELECT 1 FROM item_alias
    WHERE project_id = NEW.project_id AND alias_key = NEW.key
)
BEGIN
    SELECT RAISE(ABORT, 'the key is an alias of another item');
END;

CREATE TRIGGER item_key_update_not_alias
BEFORE UPDATE OF key ON item
WHEN EXISTS (
    SELECT 1 FROM item_alias
    WHERE project_id = NEW.project_id AND alias_key = NEW.key
)
BEGIN
    SELECT RAISE(ABORT, 'the key is an alias of another item');
END;

CREATE TRIGGER item_alias_no_update BEFORE UPDATE ON item_alias
BEGIN
    SELECT RAISE(ABORT, 'item aliases are permanent');
END;

CREATE TRIGGER item_alias_no_delete BEFORE DELETE ON item_alias
BEGIN
    SELECT RAISE(ABORT, 'item aliases are permanent');
END;

-- A decision belongs to the goal, batch or subtask it was made on and is
-- numbered by it; its key, <owner key>/decision-<number>, is derived from
-- the owner's current key and never stored.
CREATE TABLE decision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project (id),
    owner_item_id INTEGER NOT NULL,
    owner_kind TEXT NOT NULL CHECK (owner_kind IN ('goal', 'batch', 'subtask')),
    number INTEGER NOT NULL CHECK (number >= 1),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    body TEXT NOT NULL CHECK (length(body) <= 32768),
    status TEXT NOT NULL CHECK (status IN ('locked', 'deferred', 'superseded')),
    supersedes_id INTEGER CHECK (supersedes_id IS NULL OR supersedes_id <> id),
    version INTEGER NOT NULL CHECK (version >= 1),
    created_at TEXT NOT NULL CHECK (
        created_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    updated_at TEXT NOT NULL CHECK (
        updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-6][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
    ),
    UNIQUE (owner_item_id, number),
    UNIQUE (project_id, id),
    FOREIGN KEY (project_id, owner_item_id, owner_kind)
        REFERENCES item (project_id, id, kind),
    FOREIGN KEY (project_id, supersedes_id) REFERENCES decision (project_id, id)
) STRICT;

CREATE INDEX decision_project ON decision (project_id, id);
-- A decision is superseded at most once.
CREATE UNIQUE INDEX decision_supersedes ON decision (supersedes_id)
    WHERE supersedes_id IS NOT NULL;

CREATE TRIGGER decision_owner_fixed
BEFORE UPDATE OF owner_item_id, owner_kind, number, project_id ON decision
BEGIN
    SELECT RAISE(ABORT, 'a decision never changes owner or number');
END;

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
    client TEXT NOT NULL CHECK (client IN ('chat', 'code', 'paste', 'cli')),
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

-- Single-use tokens for two-phase tool calls. Only the token's SHA-256 is
-- stored: the token itself exists only in the preview result, so reading the
-- database is not enough to apply a pending change. A token is bound to one
-- project, one tool, one argument digest and one plan digest, and used_at
-- is set in the same transaction as the write it allows.
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
