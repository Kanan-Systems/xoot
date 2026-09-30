// The confirm step of a two-phase write, shared by push, move and a drop of
// an item with children: what the plan changes, then Confirm or Cancel. The
// region is always rendered so a screen reader announces what appears in it.
import type { Flow } from '../hooks/useTwoPhase.ts';
import { describeChange } from '../lib/plan.ts';
import { WriteError } from './WriteError.tsx';

interface PlanConfirmProps<Req> {
  // What is being confirmed, e.g. "Move goal-1/batch-2".
  title: string;
  flow: Flow<Req>;
  onConfirm: () => void;
  onCancel: () => void;
}

export function PlanConfirm<Req>({
  title,
  flow,
  onConfirm,
  onCancel,
}: PlanConfirmProps<Req>) {
  return (
    <div className="plan-confirm" aria-live="polite">
      {flow.step === 'sending' && <p className="muted">{title}: sending…</p>}
      {(flow.step === 'preview' || flow.step === 'confirming') && (
        <section aria-label={`Confirm: ${title}`}>
          {flow.notice !== null && <p className="warning">{flow.notice}</p>}
          <p>
            <strong>{title}</strong>: this changes {String(flow.plan.changes.length)}{' '}
            {flow.plan.changes.length === 1 ? 'item' : 'items'}.
          </p>
          <ul className="list plan-changes">
            {flow.plan.changes.map((change) => (
              <li key={change.key}>{describeChange(change)}</li>
            ))}
          </ul>
          <div className="form-actions">
            <button
              type="button"
              onClick={onConfirm}
              disabled={flow.step === 'confirming'}
            >
              Confirm
            </button>
            <button type="button" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </section>
      )}
      {flow.step === 'failed' && (
        <>
          <WriteError error={flow.error} />
          <button type="button" onClick={onCancel}>
            Dismiss
          </button>
        </>
      )}
    </div>
  );
}
