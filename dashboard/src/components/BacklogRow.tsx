// One backlog row and its actions. The actions cell sits above the link
// stretched over the row, so its buttons stay clickable. Cover turns the
// item into a subtask of a batch the rule allows; Push moves it one level
// up, always previewed and confirmed. A panel row under the row holds the
// open action.
import { useState, type SubmitEvent } from 'react';
import { Link } from 'react-router-dom';

import { useCover, usePush } from '../api/mutations.ts';
import { useTree } from '../api/queries.ts';
import type { BacklogRow as Row, PushOutput, PushRequest } from '../api/types.gen.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { useTwoPhase } from '../hooks/useTwoPhase.ts';
import { categoryClass, categoryGlyph, when } from '../lib/display.ts';
import { coverChoice, optionLabel } from '../lib/itemRules.ts';
import type { Titles } from '../lib/titles.ts';
import { PlanConfirm } from './PlanConfirm.tsx';
import { KeyLabel, KeyTag, TitleText } from './Titled.tsx';
import { WriteError } from './WriteError.tsx';
import { SelectField } from './fields.tsx';

export const COLUMNS = 7;

interface BacklogRowProps {
  prefix: string;
  row: Row;
  titles: Titles;
  onDone: (message: string) => void;
}

function pushedMessage(output: PushOutput, key: string): string {
  const moved = output.plan.changes.find((change) => change.key === key);
  const newKey = output.item?.key ?? moved?.after.key;
  return typeof newKey === 'string'
    ? `Pushed ${key} up: it is now ${newKey}.`
    : `Pushed ${key} up.`;
}

export function BacklogRow({ prefix, row, titles, onDone }: BacklogRowProps) {
  const { hrefFor } = useDrawer();
  const [covering, setCovering] = useState(false);
  const push = usePushFlow(prefix, row.key, onDone);
  const category = categoryGlyph(row.category);
  const panel = covering || push.flow.step !== 'idle';
  return (
    <>
      <tr className="row row-backlog">
        <td className="cell-title">
          <Link className="row-link" to={hrefFor(row.key)}>
            <span aria-hidden="true">⚑</span> <TitleText title={row.title} />
          </Link>
        </td>
        <td>
          <KeyTag value={row.key} />
        </td>
        <td>
          <span className={categoryClass(row.category)}>
            <span aria-hidden="true">{category.icon}</span> {row.state}
          </span>
        </td>
        <td>
          {row.found_on === null ? (
            '—'
          ) : (
            <KeyLabel itemKey={row.found_on} titles={titles} />
          )}
        </td>
        <td className="cell-why">{row.why === '' ? '—' : row.why}</td>
        <td>{when(row.created_at)}</td>
        <td className="cell-actions">
          <button
            type="button"
            aria-expanded={covering}
            aria-label={`Cover ${row.key}`}
            onClick={() => {
              setCovering(!covering);
            }}
          >
            Cover
          </button>
          {row.level !== 'project' && (
            <button
              type="button"
              aria-label={`Push ${row.key} up`}
              disabled={push.flow.step !== 'idle'}
              onClick={() => void push.start({ key: row.key })}
            >
              Push up
            </button>
          )}
        </td>
      </tr>
      {panel && (
        <tr className="row-panel">
          <td colSpan={COLUMNS}>
            {covering && (
              <CoverForm
                prefix={prefix}
                row={row}
                onDone={onDone}
                onCancel={() => {
                  setCovering(false);
                }}
              />
            )}
            <PlanConfirm
              title={`Push ${row.key} up`}
              flow={push.flow}
              onConfirm={() => void push.confirm()}
              onCancel={push.cancel}
            />
          </td>
        </tr>
      )}
    </>
  );
}

function usePushFlow(prefix: string, key: string, onDone: (message: string) => void) {
  const push = usePush(prefix);
  return useTwoPhase(
    (request: PushRequest, token: string | null) =>
      push.mutateAsync(token === null ? request : { ...request, confirm_token: token }),
    (output) => {
      onDone(pushedMessage(output, key));
    },
  );
}

interface CoverFormProps {
  prefix: string;
  row: Row;
  onDone: (message: string) => void;
  onCancel: () => void;
}

function CoverForm({ prefix, row, onDone, onCancel }: CoverFormProps) {
  const tree = useTree(prefix);
  const cover = useCover(prefix);
  const choice = coverChoice(row, tree.data?.nodes ?? []);
  const [batch, setBatch] = useState(choice.ownBatch ?? '');
  const [problem, setProblem] = useState<string | null>(null);
  const submit = (event: SubmitEvent) => {
    event.preventDefault();
    if (batch === '') {
      setProblem('Choose the batch to cover it in.');
      return;
    }
    setProblem(null);
    // The item's own batch is the server's default; only another is named.
    const named = batch === choice.ownBatch ? {} : { batch };
    cover.mutate(
      { key: row.key, ...named },
      {
        onSuccess: (output) => {
          onDone(`Covered ${row.key} with ${output.subtask.key}.`);
        },
      },
    );
  };
  return (
    <form className="write-form" aria-label={`Cover ${row.key}`} onSubmit={submit}>
      <SelectField
        label="Batch"
        value={batch}
        onChange={setBatch}
        {...(choice.ownBatch === null ? { placeholder: 'Choose a batch' } : {})}
        choices={choice.batches.map((candidate) => ({
          value: candidate.key,
          label: optionLabel(candidate),
        }))}
      />
      {problem !== null && (
        <p role="alert" className="write-error">
          {problem}
        </p>
      )}
      <WriteError error={cover.error} />
      <div className="form-actions">
        <button type="submit" disabled={cover.isPending}>
          Cover
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
