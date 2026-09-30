// Creating work and capturing backlog: a goal on the project, a batch on a
// goal, a subtask on a batch (the only kinds offered are the ones the
// hierarchy allows), and a backlog item found on any item, with a body
// saying why. The title field takes focus when a form opens.
import { useEffect, useRef, useState, type SubmitEvent } from 'react';

import { useCapture, useCreateItem } from '../api/mutations.ts';
import type { ItemWriteOutput } from '../api/types.gen.ts';
import { bodyProblem, titleProblem } from '../lib/limits.ts';
import { WriteError } from './WriteError.tsx';
import { BodyField, TitleField } from './fields.tsx';

interface FormProps {
  // Why the write is done: "Add batch", "Capture".
  label: string;
  bodyLabel: string;
  bodyRequired: boolean;
  pending: boolean;
  error: unknown;
  onSubmit: (title: string, body: string) => void;
  onCancel: () => void;
}

function TitleBodyForm(props: FormProps) {
  const { label, bodyLabel, bodyRequired, pending, error, onSubmit, onCancel } = props;
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    titleRef.current?.focus();
  }, []);
  const submit = (event: SubmitEvent) => {
    event.preventDefault();
    const missingBody =
      bodyRequired && body.trim() === '' ? 'A body saying why is required.' : null;
    const found = titleProblem(title) ?? missingBody ?? bodyProblem(body);
    setProblem(found);
    if (found === null) {
      onSubmit(title, body);
    }
  };
  return (
    <form className="write-form" aria-label={label} onSubmit={submit}>
      <TitleField label="Title" value={title} onChange={setTitle} inputRef={titleRef} />
      <BodyField
        label={bodyLabel}
        value={body}
        onChange={setBody}
        required={bodyRequired}
      />
      {problem !== null && (
        <p role="alert" className="write-error">
          {problem}
        </p>
      )}
      <WriteError error={error} />
      <div className="form-actions">
        <button type="submit" disabled={pending}>
          {label}
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

interface CreateItemFormProps {
  prefix: string;
  kind: 'goal' | 'batch' | 'subtask';
  // The goal of a batch, the batch of a subtask; null for a goal.
  parent: string | null;
  onDone: (message: string) => void;
  onCancel: () => void;
}

function created(output: ItemWriteOutput, verb: string): string {
  const reopened = output.reopened ?? [];
  const also = reopened.length > 0 ? ` Reopened: ${reopened.join(', ')}.` : '';
  return `${verb} ${output.item.key}.${also}`;
}

export function CreateItemForm({
  prefix,
  kind,
  parent,
  onDone,
  onCancel,
}: CreateItemFormProps) {
  const create = useCreateItem(prefix);
  return (
    <TitleBodyForm
      label={`Add ${kind}`}
      bodyLabel="Body (optional)"
      bodyRequired={false}
      pending={create.isPending}
      error={create.error}
      onCancel={onCancel}
      onSubmit={(title, body) => {
        create.mutate(
          { kind, title, body, ...(parent === null ? {} : { parent }) },
          {
            onSuccess: (output) => {
              onDone(created(output, 'Created'));
            },
          },
        );
      }}
    />
  );
}

interface CaptureFormProps {
  prefix: string;
  foundOn: string;
  onDone: (message: string) => void;
  onCancel: () => void;
}

export function CaptureForm({ prefix, foundOn, onDone, onCancel }: CaptureFormProps) {
  const capture = useCapture(prefix);
  return (
    <TitleBodyForm
      label="Capture"
      bodyLabel="Why it needs doing"
      bodyRequired
      pending={capture.isPending}
      error={capture.error}
      onCancel={onCancel}
      onSubmit={(title, body) => {
        capture.mutate(
          { found_on: foundOn, title, body },
          {
            onSuccess: (output) => {
              onDone(created(output, 'Captured'));
            },
          },
        );
      }}
    />
  );
}
