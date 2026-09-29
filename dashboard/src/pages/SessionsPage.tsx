// /:project/sessions: the sessions table (closed ones hidden unless
// ?closed=1) and, with ?session=<key>, that session's detail.
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { useSessions } from '../api/queries.ts';
import type { SessionRow } from '../api/types.gen.ts';
import { QueryState } from '../components/QueryState.tsx';
import { SessionDetail } from '../components/SessionDetail.tsx';
import { TabHelp } from '../components/TabHelp.tsx';
import { Titled } from '../components/Titled.tsx';
import { PARAM, withParam } from '../lib/search.ts';

function when(value: string | null): string {
  return value === null ? '—' : value.slice(0, 16).replace('T', ' ');
}

export function SessionsPage() {
  const { project = '' } = useParams();
  const [search, setSearch] = useSearchParams();
  const query = useSessions(project);
  const showClosed = search.get(PARAM.closed) === '1';
  const selected = search.get(PARAM.session);
  return (
    <div className="view view-split">
      <div>
        <h1 className="view-title">Sessions</h1>
        <TabHelp tab="sessions" />
        <label>
          <input
            type="checkbox"
            checked={showClosed}
            onChange={(event) => {
              const value = event.target.checked ? '1' : null;
              setSearch(new URLSearchParams(withParam(search, PARAM.closed, value)));
            }}
          />{' '}
          Show closed sessions
        </label>
        <QueryState query={query} what="sessions">
          {(view) => (
            <SessionsTable
              rows={view.sessions.filter((s) => showClosed || s.status === 'open')}
              selected={selected}
              search={search}
            />
          )}
        </QueryState>
      </div>
      {selected !== null && <SessionDetail prefix={project} sessionKey={selected} />}
    </div>
  );
}

interface SessionsTableProps {
  rows: readonly SessionRow[];
  selected: string | null;
  search: URLSearchParams;
}

function SessionsTable({ rows, selected, search }: SessionsTableProps) {
  if (rows.length === 0) {
    return <p className="muted">No sessions to show.</p>;
  }
  return (
    <table className="items">
      <caption className="visually-hidden">Sessions</caption>
      <thead>
        <tr>
          <th scope="col">Title</th>
          <th scope="col">Client</th>
          <th scope="col">Status</th>
          <th scope="col">Started</th>
          <th scope="col">Closed</th>
          <th scope="col">Linked items</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.key}
            className={row.key === selected ? 'row row-selected' : 'row'}
            aria-current={row.key === selected ? 'true' : undefined}
          >
            <td className="cell-title">
              <Link
                className="row-link"
                to={{ search: withParam(search, PARAM.session, row.key) }}
              >
                <Titled title={row.title} itemKey={row.key} />
              </Link>
            </td>
            <td>{row.client}</td>
            <td>
              <span className={`status status-${row.status}`}>
                <span aria-hidden="true">{row.status === 'open' ? '●' : '○'}</span>{' '}
                {row.status}
              </span>
            </td>
            <td>{when(row.started_at)}</td>
            <td>{when(row.closed_at)}</td>
            <td>{row.linked_items}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
