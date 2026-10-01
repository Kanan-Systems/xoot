// The confirm step of a two-phase write, shared by push, move and a drop of
// an item with children: what the plan changes in plain words when the
// titles are known, then where the item was and where it goes as a
// staircase of titles (never the plan's raw key, parent or number fields),
// then Confirm or Cancel. The region is always rendered so a screen reader
// announces what appears in it.
import type { SubtreeOutput } from '../api/types.gen.ts';
import type { Flow } from '../hooks/useTwoPhase.ts';
import type { Journey } from '../lib/journey.ts';
import { JourneyView } from './JourneyView.tsx';
import { WriteError } from './WriteError.tsx';

interface ConfirmPanelProps {
  // What is being confirmed, e.g. "Move goal-1/batch-2".
  title: string;
  // The plain-language sentence; null says only how many items change.
  summary: string | null;
  journey: Journey;
  // How many items the plan changes, when there is a plan.
  count?: number | null;
  notice?: string | null;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

// Also used before anything is sent, where there is no count yet.
export function ConfirmPanel(props: ConfirmPanelProps) {
  const {
    title,
    summary,
    journey,
    count = null,
    notice = null,
    busy = false,
    onConfirm,
    onCancel,
  } = props;
  return (
    <section aria-label={`Confirm: ${title}`}>
      {notice !== null && <p className="warning">{notice}</p>}
      {summary === null ? (
        <p>
          <strong>{title}</strong>
          {count === null
            ? '?'
            : `: this changes ${String(count)} ${count === 1 ? 'item' : 'items'}.`}
        </p>
      ) : (
        <p className="plan-summary">{summary}</p>
      )}
      <JourneyView journey={journey} />
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
  // Plain words for the plan, or null to say only how many items change.
  summarize?: (plan: SubtreeOutput) => string | null;
  journey: (plan: SubtreeOutput) => Journey;
  onConfirm: () => void;
  onCancel: () => void;
}

export function PlanConfirm<Req>({
  title,
  flow,
  summarize,
  journey,
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
          journey={journey(flow.plan)}
          count={flow.plan.changes.length}
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
