// The backlog view's tables, in order: each open session, the project
// backlog, then unfiled subtasks.
import type { BacklogRow, BacklogsView } from '../api/types.gen.ts';

export interface BacklogGroup {
  id: string;
  heading: string;
  items: BacklogRow[];
  truncated: boolean;
}

export function backlogGroups(view: BacklogsView): BacklogGroup[] {
  const sessions = view.sessions
    .filter((entry) => entry.session.status === 'open')
    .map((entry) => ({
      id: `session-${entry.session.key}`,
      heading: `${entry.session.key}: ${entry.session.title}`,
      items: entry.items,
      truncated: entry.truncated,
    }));
  return [
    ...sessions,
    {
      id: 'project',
      heading: 'Project backlog',
      items: view.project_backlog,
      truncated: view.project_backlog_truncated,
    },
    {
      id: 'unfiled',
      heading: 'Unfiled',
      items: view.unfiled,
      truncated: view.unfiled_truncated,
    },
  ];
}
