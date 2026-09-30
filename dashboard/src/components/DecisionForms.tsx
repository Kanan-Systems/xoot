// Recording a decision on a goal, batch or subtask (optionally superseding
// an older one of the same goal), and editing one in place: title, body and
// status, sent with the version the edit started from, so a change made
// meanwhile comes back as a conflict naming the fields and actors.
import { useEffect, useRef, useState, type SubmitEvent } from 'react';

import { useCreateDecision, useUpdateDecision } from '../api/mutations.ts';
import { useDecision, useDecisions, useTree } from '../api/queries.ts';
import type {
  DecisionDetail,
  DecisionStatus,
  DecisionUpdateRequest,
} from '../api/types.gen.ts';
import { DECISION_STATUS, truncate } from '../lib/display.ts';
import { decisionOwners, optionLabel } from '../lib/itemRules.ts';
import { goalOf } from '../lib/keys.ts';
import { bodyProblem, titleProblem } from '../lib/limits.ts';
import { QueryState } from './QueryState.tsx';
import { WriteError } from './WriteError.tsx';
import { BodyField, ChoiceField, SelectField, TitleField } from './fields.tsx';

const NEW_STATUSES: readonly DecisionStatus[] = ['locked', 'deferred'];

function statusChoices(current: DecisionStatus | null) {
  const statuses =
    current === null || NEW_STATUSES.includes(current)
      ? NEW_STATUSES
      : [current, ...NEW_STATUSES];
  return statuses.map((status) => ({
    value: status,
    label: DECISION_STATUS[status].label,
  }));
}

function isStatus(value: string): value is DecisionStatus {
  return value in DECISION_STATUS;
}

function Problem({ text }: { text: string | null }) {
  return text === null ? null : (
    <p role="alert" className="write-error">
      {text}
    </p>
  );
}

interface DecisionFormProps {
  prefix: string;
  // The owner offered first: the drawer's item.
  owner: string;
  onDone: (message: string) => void;
  onCancel: () => void;
}

export function DecisionForm({
  prefix,
  owner: initialOwner,
  onDone,
  onCancel,
}: DecisionFormProps) {
  const tree = useTree(prefix);
  const decisions = useDecisions(prefix);
  const create = useCreateDecision(prefix);
  const [owner, setOwner] = useState(initialOwner);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [status, setStatus] = useState<DecisionStatus>('locked');
  const [supersedes, setSupersedes] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    titleRef.current?.focus();
  }, []);
  const goal = goalOf(owner);
  const older = (decisions.data?.decisions ?? []).filter(
    (d) => d.owner !== null && goalOf(d.owner) === goal && d.status !== 'superseded',
  );
  const submit = (event: SubmitEvent) => {
    event.preventDefault();
    const found = titleProblem(title) ?? bodyProblem(body);
    setProblem(found);
    if (found !== null) {
      return;
    }
    create.mutate(
      { owner, title, body, status, ...(supersedes === '' ? {} : { supersedes }) },
      {
        onSuccess: (output) => {
          onDone(`Recorded ${output.decision.key}.`);
        },
      },
    );
  };
  return (
    <form className="write-form" aria-label="Record decision" onSubmit={submit}>
      <SelectField
        label="Made on"
        value={owner}
        onChange={(value) => {
          setOwner(value);
          setSupersedes('');
        }}
        choices={decisionOwners(tree.data?.nodes ?? []).map((candidate) => ({
          value: candidate.key,
          label: optionLabel(candidate),
        }))}
      />
      <TitleField label="Title" value={title} onChange={setTitle} inputRef={titleRef} />
      <BodyField label="Body (optional)" value={body} onChange={setBody} />
      <ChoiceField
        label="Status"
        value={status}
        onChange={(value) => {
          if (isStatus(value)) {
            setStatus(value);
          }
        }}
        choices={statusChoices(null)}
      />
      <SelectField
        label="Supersedes (optional)"
        value={supersedes}
        onChange={setSupersedes}
        placeholder="Nothing"
        choices={older.map((d) => ({
          value: d.key,
          label: `${truncate(d.title).text} (${d.key})`,
        }))}
      />
      <Problem text={problem} />
      <WriteError error={create.error} />
      <div className="form-actions">
        <button type="submit" disabled={create.isPending}>
          Record decision
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

interface DecisionEditorProps {
  prefix: string;
  decisionKey: string;
  onDone: (message: string) => void;
  onCancel: () => void;
}

// The body is not in the list row, so the editor loads the decision first.
export function DecisionEditor({
  prefix,
  decisionKey,
  onDone,
  onCancel,
}: DecisionEditorProps) {
  const query = useDecision(prefix, decisionKey, true);
  return (
    <QueryState query={query} what="decision">
      {(view) => (
        <DecisionFields
          prefix={prefix}
          detail={view.decision}
          onDone={onDone}
          onCancel={onCancel}
        />
      )}
    </QueryState>
  );
}

interface DecisionFieldsProps {
  prefix: string;
  // The stored decision, refreshed by polling; the draft starts from the
  // first one seen and is never overwritten.
  detail: DecisionDetail;
  onDone: (message: string) => void;
  onCancel: () => void;
}

function DecisionFields({ prefix, detail, onDone, onCancel }: DecisionFieldsProps) {
  const [base] = useState(detail);
  const [title, setTitle] = useState(base.title);
  const [body, setBody] = useState(base.body);
  const [status, setStatus] = useState<DecisionStatus>(base.status);
  const [problem, setProblem] = useState<string | null>(null);
  const update = useUpdateDecision(prefix);
  const titleRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    titleRef.current?.focus();
  }, []);
  const submit = (event: SubmitEvent) => {
    event.preventDefault();
    const request: DecisionUpdateRequest = { expected_version: base.version };
    if (title !== base.title) request.title = title;
    if (body !== base.body) request.body = body;
    if (status !== base.status) request.status = status;
    if (Object.keys(request).length === 1) {
      onCancel();
      return;
    }
    const found =
      (request.title === undefined ? null : titleProblem(title)) ?? bodyProblem(body);
    setProblem(found);
    if (found === null) {
      update.mutate(
        { key: base.key, body: request },
        {
          onSuccess: () => {
            onDone(`Saved ${base.key}.`);
          },
        },
      );
    }
  };
  return (
    <form className="write-form" aria-label={`Edit ${base.key}`} onSubmit={submit}>
      {detail.version !== base.version && (
        <p className="warning" role="status">
          This decision changed while you were editing. Saving will be refused; cancel
          to see the change.
        </p>
      )}
      <TitleField label="Title" value={title} onChange={setTitle} inputRef={titleRef} />
      <BodyField label="Body" value={body} onChange={setBody} />
      <ChoiceField
        label="Status"
        value={status}
        onChange={(value) => {
          if (isStatus(value)) {
            setStatus(value);
          }
        }}
        choices={statusChoices(base.status)}
      />
      <Problem text={problem} />
      <WriteError error={update.error} />
      <div className="form-actions">
        <button type="submit" disabled={update.isPending}>
          Save
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
