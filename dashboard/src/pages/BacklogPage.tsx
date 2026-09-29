// /:project/backlog: every backlog in one place.
import { useParams } from 'react-router-dom';

import { useBacklogs } from '../api/queries.ts';
import { BacklogsSection } from '../components/BacklogsSection.tsx';
import { QueryState } from '../components/QueryState.tsx';

export function BacklogPage() {
  const { project = '' } = useParams();
  const query = useBacklogs(project);
  return (
    <div className="view">
      <h1 className="view-title">Backlog</h1>
      <QueryState query={query} what="backlogs">
        {(view) => <BacklogsSection view={view} />}
      </QueryState>
    </div>
  );
}
