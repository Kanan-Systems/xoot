// The tree toolbar: the tab help, the show-done toggle and the cut warning.
// The tree has no heading, so its help leads the toolbar.
import { TabHelp } from './TabHelp.tsx';

interface TreeToolbarProps {
  showDone: boolean;
  onShowDone: (show: boolean) => void;
  truncated: boolean;
}

export function TreeToolbar({ showDone, onShowDone, truncated }: TreeToolbarProps) {
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
      {truncated && <span className="warning">The tree was cut at 1000 items.</span>}
    </div>
  );
}
