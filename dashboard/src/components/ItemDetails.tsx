// What the drawer shows for one item. The title is the heading, in full;
// kind and key are secondary. Every stored string is rendered as a text
// node: bodies keep their whitespace in <pre>, nothing is parsed as
// markdown or HTML.
import type { ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import type { ItemView } from '../api/types.gen.ts';
import { useDrawer } from '../hooks/useDrawer.ts';
import { categoryClass, categoryGlyph, DECISION_STATUS, KIND } from '../lib/display.ts';
import { completionState, historyLine } from '../lib/history.ts';
import { PARAM } from '../lib/search.ts';
import { NO_TITLES, type Titles } from '../lib/titles.ts';
import { KeyLabel, KeyTag, TitleText } from './Titled.tsx';

interface ItemDetailsProps {
  prefix: string;
  view: ItemView;
  titles?: Titles;
  // How many open backlog items hold this goal or batch open, if any.
  openBacklog?: number | undefined;
  // The drawer's write controls, under the heading.
  children?: ReactNode;
}

export function ItemDetails({
  prefix,
  view,
  titles = NO_TITLES,
  openBacklog,
  children,
}: ItemDetailsProps) {
  const { item } = view;
  const navigate = useNavigate();
  const category = categoryGlyph(item.category);
  const focusable = item.kind === 'goal' || item.kind === 'batch';
  const completion = completionState(item, view.events, openBacklog);
  return (
    <>
      <h2 className="detail-title">{item.title}</h2>
      <p className="detail-meta">
        <span aria-hidden="true">{KIND[item.kind].icon}</span> {KIND[item.kind].label}{' '}
        <KeyTag value={item.key} />
      </p>
      {focusable && (
        <button
          type="button"
          className="action"
          onClick={() => {
            const search = new URLSearchParams({ [PARAM.focus]: item.key });
            void navigate({
              pathname: `/${prefix}/tree`,
              search: `?${search.toString()}`,
            });
          }}
        >
          ⌖ Focus on this {item.kind}
        </button>
      )}
      {children}
      <dl className="facts">
        <dt>State</dt>
        <dd>
          <span className={categoryClass(item.category)}>
            <span aria-hidden="true">{category.icon}</span> {item.state} (
            {category.label})
          </span>
        </dd>
        {completion !== null && (
          <>
            <dt>Completion</dt>
            <dd className={openBacklog === undefined ? undefined : 'warning'}>
              {completion}
            </dd>
          </>
        )}
        <dt>Version</dt>
        <dd>{item.version}</dd>
        <dt>Parent</dt>
        <dd>
          <ItemLink itemKey={item.parent} titles={titles} none="the project" />
        </dd>
        {item.kind === 'backlog' && (
          <>
            <dt>Found on</dt>
            <dd>
              <ItemLink itemKey={item.found_on} titles={titles} none="not recorded" />
            </dd>
            <dt>Covered by</dt>
            <dd>
              <ItemLink itemKey={item.covered_by} titles={titles} none="not covered" />
            </dd>
          </>
        )}
        {item.origin !== null && (
          <>
            <dt>Origin</dt>
            <dd>
              <ItemLink itemKey={item.origin} titles={titles} none="" />
            </dd>
          </>
        )}
        {item.awaiting_decision !== null && (
          <>
            <dt>Awaiting</dt>
            <dd>
              <KeyLabel itemKey={item.awaiting_decision} titles={titles} />
            </dd>
          </>
        )}
        <dt>Old keys</dt>
        <dd>
          {item.aliases.length === 0 ? (
            <span className="muted">none</span>
          ) : (
            <ul className="list aliases">
              {item.aliases.map((alias) => (
                <li key={alias}>
                  <KeyTag value={alias} />
                </li>
              ))}
            </ul>
          )}
        </dd>
      </dl>
      <h3>Body</h3>
      {item.body === '' ? (
        <p className="muted">No body.</p>
      ) : (
        <pre className="body">{item.body}</pre>
      )}
      <h3>Decisions</h3>
      {view.decisions.length === 0 ? (
        <p className="muted">No decisions made on this item.</p>
      ) : (
        view.decisions.map((decision) => (
          <article key={decision.key} className="decision">
            <h4>
              <TitleText title={decision.title} /> <KeyTag value={decision.key} />{' '}
              {DECISION_STATUS[decision.status].label}
            </h4>
            <pre className="body">{decision.body}</pre>
          </article>
        ))
      )}
      <h3>Recent history</h3>
      <ol className="history">
        {view.events.map((event, index) => (
          <li key={`${event.created_at}-${String(index)}`}>{historyLine(event)}</li>
        ))}
      </ol>
    </>
  );
}

interface ItemLinkProps {
  itemKey: string | null;
  titles: Titles;
  none: string;
}

// A link that opens another item's drawer, shown as "title (key)".
function ItemLink({ itemKey, titles, none }: ItemLinkProps): ReactNode {
  const { hrefFor } = useDrawer();
  if (itemKey === null) {
    return <span className="muted">{none}</span>;
  }
  return (
    <Link to={hrefFor(itemKey)}>
      <KeyLabel itemKey={itemKey} titles={titles} />
    </Link>
  );
}
