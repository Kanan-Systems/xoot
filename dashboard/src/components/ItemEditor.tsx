// Editing an item in the drawer: an explicit draft of title, state and body,
// taken once when editing starts. Polling may refetch the item meanwhile;
// the draft is never overwritten. If the stored version moves, a banner
// says so, and Save still sends the version the edit started from, so the
// server refuses it with the conflicting fields and actors: no merge, no
// retry. A drop of an item with children goes through the plan confirm.
import { useEffect, useRef, useState, type SubmitEvent } from 'react';

import { useUpdateItem } from '../api/mutations.ts';
import { useWorkflow } from '../api/queries.ts';
import type {
  ItemUpdateOutput,
  ItemUpdateRequest,
  ItemView,
} from '../api/types.gen.ts';
import { useTitles } from '../hooks/useTitles.ts';
import { useTwoPhase } from '../hooks/useTwoPhase.ts';
import { CATEGORY } from '../lib/display.ts';
import { editRequest, stateOptions, type Base } from '../lib/itemEdit.ts';
import { dropJourney } from '../lib/journey.ts';
import type { Titles } from '../lib/titles.ts';
import { dropPlanText, dropResultText } from '../lib/wording.ts';
import { PlanConfirm } from './PlanConfirm.tsx';
import { BodyField, SelectField, TitleField } from './fields.tsx';

interface ItemEditorProps {
  prefix: string;
  view: ItemView;
  onClose: () => void;
  onSaved: (message: string) => void;
}

function savedMessage(output: ItemUpdateOutput, key: string, titles: Titles): string {
  const completed = output.completed ?? [];
  const reopened = output.reopened ?? [];
  const dropped =
    output.plan === null ? null : dropResultText(key, output.plan, titles);
  const parts = [
    output.mode === 'drop'
      ? (dropped ?? `Dropped ${key} with its children.`)
      : `Saved ${key}.`,
  ];
  if (completed.length > 0) parts.push(`Completed: ${completed.join(', ')}.`);
  if (reopened.length > 0) parts.push(`Reopened: ${reopened.join(', ')}.`);
  return parts.join(' ');
}

export function ItemEditor({ prefix, view, onClose, onSaved }: ItemEditorProps) {
  const { item } = view;
  const [base] = useState<Base & { key: string }>(() => ({
    key: item.key,
    title: item.title,
    body: item.body,
    state: item.state,
    version: item.version,
    hasChildren: view.children.total > 0,
  }));
  const [title, setTitle] = useState(base.title);
  const [body, setBody] = useState(base.body);
  const [state, setState] = useState(base.state);
  const [problem, setProblem] = useState<string | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const workflow = useWorkflow(prefix);
  const titles = useTitles(prefix);
  const update = useUpdateItem(prefix);
  const save = useTwoPhase(
    (request: ItemUpdateRequest, token: string | null) =>
      update.mutateAsync({
        key: base.key,
        body: token === null ? request : { ...request, confirm_token: token },
      }),
    (output) => {
      onSaved(savedMessage(output, base.key, titles));
    },
  );
  useEffect(() => {
    titleRef.current?.focus();
  }, []);

  const options = stateOptions(
    workflow.data?.workflow[item.kind],
    base.state,
    item.category,
  );
  const busy = save.flow.step !== 'idle' && save.flow.step !== 'failed';
  const submit = (event: SubmitEvent) => {
    event.preventDefault();
    const category = options.find((spec) => spec.name === state)?.category;
    const result = editRequest(base, { title, body, state }, category);
    if (result.kind === 'unchanged') {
      onClose();
    } else if (result.kind === 'problem') {
      setProblem(result.message);
    } else {
      setProblem(null);
      void save.start(result.request);
    }
  };

  return (
    <form className="write-form" aria-label={`Edit ${base.key}`} onSubmit={submit}>
      {item.version !== base.version && (
        <p className="warning" role="status">
          This item changed while you were editing (version {base.version} is now{' '}
          {item.version}). Saving will be refused; cancel to see the change.
        </p>
      )}
      <TitleField label="Title" value={title} onChange={setTitle} inputRef={titleRef} />
      <SelectField
        label="State"
        value={state}
        onChange={setState}
        choices={options.map((spec) => ({
          value: spec.name,
          label: `${spec.name} (${CATEGORY[spec.category].label})`,
        }))}
      />
      <BodyField label="Body" value={body} onChange={setBody} />
      {problem !== null && (
        <p role="alert" className="write-error">
          {problem}
        </p>
      )}
      <div className="form-actions">
        <button type="submit" disabled={busy}>
          Save
        </button>
        <button type="button" onClick={onClose}>
          Cancel
        </button>
      </div>
      <PlanConfirm
        title={`Save ${base.key}`}
        flow={save.flow}
        summarize={(plan) => dropPlanText(base.key, plan, titles)}
        journey={(plan) => dropJourney(base.key, plan, titles)}
        onConfirm={() => void save.confirm()}
        onCancel={save.cancel}
      />
    </form>
  );
}
