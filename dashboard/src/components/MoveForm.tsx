// "Move to…" in the drawer: the keyboard path for what the tree does by
// drag and drop. Targets are every item of the parent kind but the current
// parent, from the tree the views already share.
import { useState, type SubmitEvent } from 'react';

import { useTree } from '../api/queries.ts';
import type { ItemDetail } from '../api/types.gen.ts';
import { movedMessage, useMoveFlow } from '../hooks/useMoveFlow.ts';
import { useTitles } from '../hooks/useTitles.ts';
import { moveTargets, optionLabel } from '../lib/itemRules.ts';
import { moveFactsFromPlan, movePlanText } from '../lib/wording.ts';
import { PlanConfirm } from './PlanConfirm.tsx';
import { SelectField } from './fields.tsx';

interface MoveFormProps {
  prefix: string;
  item: ItemDetail;
  onDone: (message: string) => void;
  onCancel: () => void;
}

export function MoveForm({ prefix, item, onDone, onCancel }: MoveFormProps) {
  const tree = useTree(prefix);
  const [parent, setParent] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  const titles = useTitles(prefix);
  const flow = useMoveFlow(prefix, (output, request) => {
    onDone(movedMessage(output, request, titles));
  });
  const targets = moveTargets(item, tree.data?.nodes ?? []);
  const submit = (event: SubmitEvent) => {
    event.preventDefault();
    if (parent === '') {
      setProblem('Choose where to move it.');
      return;
    }
    setProblem(null);
    void flow.start({ key: item.key, parent, expected_version: item.version });
  };
  return (
    <form className="write-form" aria-label={`Move ${item.key}`} onSubmit={submit}>
      <SelectField
        label="New parent"
        value={parent}
        onChange={setParent}
        placeholder={targets.length === 0 ? 'Nowhere to move it' : 'Choose…'}
        choices={targets.map((target) => ({
          value: target.key,
          label: optionLabel(target),
        }))}
      />
      {problem !== null && (
        <p role="alert" className="write-error">
          {problem}
        </p>
      )}
      <div className="form-actions">
        <button type="submit" disabled={flow.flow.step !== 'idle'}>
          Move
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <PlanConfirm
        title={`Move ${item.key}`}
        flow={flow.flow}
        summarize={(plan) =>
          movePlanText(moveFactsFromPlan(item.key, parent, plan), titles)
        }
        onConfirm={() => void flow.confirm()}
        onCancel={flow.cancel}
      />
    </form>
  );
}
