// The confirm step of a two-phase write, shared by push, move and a drop of
// an item with children: what the plan changes in plain words when the
// titles are known (the raw field changes stay under "Details"), then
// Confirm or Cancel. The region is always rendered so a screen reader
// announces what appears in it.
import type { SubtreeOutput } from '../api/types.gen.ts';
import type { Flow } from '../hooks/useTwoPhase.ts';
import { describeChange } from '../lib/plan.ts';
import { WriteError } from './WriteError.tsx';

interface ConfirmPanelProps {
  // What is being confirmed, e.g. "Move goal-1/batch-2".
  title: string;
  // The plain-language sentence; null shows the raw lines instead.
  summary: string | null;
  lines: readonly string[];
  notice?: string | null;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

// Also used before anything is sent, where the lines are empty.
export function ConfirmPanel(props: ConfirmPanelProps) {
  const {
    title,
    summary,
    lines,
    notice = null,
    busy = false,
    onConfirm,
    onCancel,
  } = props;
  const list = (
    <ul className="list plan-changes">
      {lines.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  );
  return (
    <section aria-label={`Confirm: ${title}`}>
      {notice !== null && <p className="warning">{notice}</p>}
      {summary === null ? (
        <>
          <p>
            <strong>{title}</strong>: this changes {String(lines.length)}{' '}
            {lines.length === 1 ? 'item' : 'items'}.
          </p>
          {list}
        </>
      ) : (
        <>
          <p className="plan-summary">{summary}</p>
          {lines.length > 0 && (
            <details className="plan-details">
              <summary>Details</summary>
              {list}
            </details>
          )}
        </>
      )}
      <div className="form-actions">
        <button type="button" onClick={onConfirm} disabled={busy}>
          Confirm
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </section>
  );
}

interface PlanConfirmProps<Req> {
  title: string;
  flow: Flow<Req>;
  // Plain words for the plan, or null to fall back to the raw changes.
  summarize?: (plan: SubtreeOutput) => string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export function PlanConfirm<Req>({
  title,
  flow,
  summarize,
  onConfirm,
  onCancel,
}: PlanConfirmProps<Req>) {
  return (
    <div className="plan-confirm" aria-live="polite">
      {flow.step === 'sending' && <p className="muted">{title}: sending…</p>}
      {(flow.step === 'preview' || flow.step === 'confirming') && (
        <ConfirmPanel
          title={title}
          summary={summarize?.(flow.plan) ?? null}
          lines={flow.plan.changes.map(describeChange)}
          notice={flow.notice}
          busy={flow.step === 'confirming'}
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
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
