// The backlog view's tables, in order: each open session, the project
// backlog, then unfiled subtasks. A session group is headed by its title,
// with its key as the secondary label.
import type { BacklogRow, BacklogsView } from '../api/types.gen.ts';

export interface BacklogGroup {
  id: string;
  heading: string;
  key: string | null;
  items: BacklogRow[];
  truncated: boolean;
}

export function backlogGroups(view: BacklogsView): BacklogGroup[] {
  const sessions = view.sessions
    .filter((entry) => entry.session.status === 'open')
    .map((entry) => ({
      id: `session-${entry.session.key}`,
      heading: entry.session.title,
      key: entry.session.key,
      items: entry.items,
      truncated: entry.truncated,
    }));
  return [
    ...sessions,
    {
      id: 'project',
      heading: 'Project backlog',
      key: null,
      items: view.project_backlog,
      truncated: view.project_backlog_truncated,
    },
    {
      id: 'unfiled',
      heading: 'Unfiled',
      key: null,
      items: view.unfiled,
      truncated: view.unfiled_truncated,
    },
  ];
}
