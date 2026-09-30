// /:project/backlog: every open backlog item, by level.
import { useParams } from 'react-router-dom';

import { useBacklog } from '../api/queries.ts';
import { BacklogsSection } from '../components/BacklogsSection.tsx';
import { QueryState } from '../components/QueryState.tsx';
import { TabHelp } from '../components/TabHelp.tsx';
import { useTitles } from '../hooks/useTitles.ts';

export function BacklogPage() {
  const { project = '' } = useParams();
  const query = useBacklog(project);
  const titles = useTitles(project);
  return (
    <div className="view">
      <h1 className="view-title">Backlog</h1>
      <TabHelp tab="backlog" />
      <QueryState query={query} what="backlog">
        {(view) => <BacklogsSection prefix={project} view={view} titles={titles} />}
      </QueryState>
    </div>
  );
}
