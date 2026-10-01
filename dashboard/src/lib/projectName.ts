// A project segment typed into the URL: the key prefix the dashboard builds
// its URLs from, or an alias, which redirects to the prefix URL. Prefixes
// and aliases share one namespace on the server, so at most one matches.
import type { ProjectInfo } from '../api/types.gen.ts';

export type ProjectName =
  { kind: 'prefix' } | { kind: 'alias'; prefix: string } | { kind: 'unknown' };

export function resolveProjectName(
  projects: readonly ProjectInfo[],
  name: string,
): ProjectName {
  if (projects.some((project) => project.key_prefix === name)) {
    return { kind: 'prefix' };
  }
  const owner = projects.find((project) => project.aliases.includes(name));
  return owner === undefined
    ? { kind: 'unknown' }
    : { kind: 'alias', prefix: owner.key_prefix };
}

// The same path with its first segment (the project) replaced.
export function withProject(pathname: string, prefix: string): string {
  const rest = pathname.split('/').slice(2).join('/');
  return rest === '' ? `/${prefix}` : `/${prefix}/${rest}`;
}
