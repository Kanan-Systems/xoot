// A plan as origin, then destination: two indented staircases, the second
// under an arrow. Depth is a class, since the CSP allows no inline styles.
import type { Journey, Step } from '../lib/journey.ts';

const DEEPEST = 4;

function Stair({ steps, label }: { steps: readonly Step[]; label: string }) {
  return (
    <ul className="stair" aria-label={label}>
      {steps.map((step, index) => (
        <li
          // Fixed per plan; two items may share a title and depth.
          key={index}
          className={`stair-${String(Math.min(step.depth, DEEPEST))}`}
        >
          {step.text}
          {step.note !== null && <span className="muted"> ({step.note})</span>}
        </li>
      ))}
    </ul>
  );
}

export function JourneyView({ journey }: { journey: Journey }) {
  if (journey.to.length === 0) {
    return (
      <div className="journey">
        <Stair steps={journey.from} label="Dropped" />
      </div>
    );
  }
  return (
    <div className="journey">
      <Stair steps={journey.from} label="From" />
      <div className="journey-to">
        <span className="journey-arrow" aria-hidden="true">
          →
        </span>
        <Stair steps={journey.to} label="To" />
      </div>
    </div>
  );
}
