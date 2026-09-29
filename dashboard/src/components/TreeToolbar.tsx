// The tree toolbar: the tab help, the show-done toggle and the session filter
// (a session, then "highlight" or "only this session"). The tree has no
// heading, so its help leads the toolbar.
import { useId } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useSessions } from '../api/queries.ts';
import { truncate } from '../lib/display.ts';
import { filterMode, PARAM, withParam, type FilterMode } from '../lib/search.ts';
import { TabHelp } from './TabHelp.tsx';

interface TreeToolbarProps {
  prefix: string;
  showDone: boolean;
  onShowDone: (show: boolean) => void;
  truncated: boolean;
}

const MODES: readonly { value: FilterMode; label: string }[] = [
  { value: 'highlight', label: 'Highlight' },
  { value: 'only', label: 'Only this session' },
];

export function TreeToolbar({
  prefix,
  showDone,
  onShowDone,
  truncated,
}: TreeToolbarProps) {
  const sessions = useSessions(prefix);
  const [search, setSearch] = useSearchParams();
  const modeName = useId();
  const selected = search.get(PARAM.session);
  const mode = filterMode(search.get(PARAM.mode));
  const update = (name: string, value: string | null) => {
    setSearch(new URLSearchParams(withParam(search, name, value)));
  };
  return (
    <div className="tree-toolbar">
      <TabHelp tab="tree" />
      <label>
        <input
          type="checkbox"
          checked={showDone}
          onChange={(event) => {
            onShowDone(event.target.checked);
          }}
        />{' '}
        Show done and dropped
      </label>
      <label className="control">
        Session{' '}
        <select
          value={selected ?? ''}
          onChange={(event) => {
            update(
              PARAM.session,
              event.target.value === '' ? null : event.target.value,
            );
          }}
        >
          <option value="">No session filter</option>
          {(sessions.data?.sessions ?? []).map((session) => (
            <option key={session.key} value={session.key}>
              {truncate(session.title).text} ({session.key}, {session.status})
            </option>
          ))}
        </select>
      </label>
      <fieldset className="modes" disabled={selected === null}>
        <legend>Filter mode</legend>
        {MODES.map((option) => (
          <label key={option.value}>
            <input
              type="radio"
              name={modeName}
              value={option.value}
              checked={mode === option.value}
              onChange={() => {
                update(PARAM.mode, option.value);
              }}
            />{' '}
            {option.label}
          </label>
        ))}
      </fieldset>
      {truncated && <span className="warning">The tree was cut at 1000 items.</span>}
    </div>
  );
}
