// One project: the top bar, the current view (a child route) and the shared
// detail drawer. Polling lives here so every view refreshes live.
import { Outlet, useParams } from 'react-router-dom';

import { DetailPanel } from '../components/DetailPanel.tsx';
import { TopBar } from '../components/TopBar.tsx';
import { useChangesPolling } from '../hooks/useChangesPolling.ts';

export function ProjectPage() {
  const { project = '' } = useParams();
  const poll = useChangesPolling(project);
  return (
    <div className="page">
      <TopBar prefix={project} checkedAt={poll.checkedAt} failing={poll.failing} />
      <main className="main">
        <Outlet />
      </main>
      <DetailPanel prefix={project} />
    </div>
  );
}
