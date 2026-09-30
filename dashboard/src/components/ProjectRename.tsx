// Renaming the project or adding an alias, next to the project switcher.
// The key prefix never changes, so no URL goes stale; the project list is
// refreshed by the mutation, since polling never reloads it.
import { useEffect, useRef, useState, type SubmitEvent } from 'react';

import { useRenameProject } from '../api/mutations.ts';
import { useProjects } from '../api/queries.ts';
import type { ProjectRenameRequest } from '../api/types.gen.ts';
import { aliasProblem, LIMITS } from '../lib/limits.ts';
import { Disclosure } from './Disclosure.tsx';
import { WriteError } from './WriteError.tsx';

export function ProjectRename({ prefix }: { prefix: string }) {
  const [notice, setNotice] = useState('');
  return (
    <div className="project-rename">
      <Disclosure label="Rename">
        {(close) => (
          <RenameForm
            prefix={prefix}
            onDone={(message) => {
              close();
              setNotice(message);
            }}
            onCancel={close}
          />
        )}
      </Disclosure>
      <span role="status" className="notice">
        {notice}
      </span>
    </div>
  );
}

interface RenameFormProps {
  prefix: string;
  onDone: (message: string) => void;
  onCancel: () => void;
}

// What to send, or why nothing can be.
function renameRequest(
  current: string,
  name: string,
  alias: string,
): ProjectRenameRequest | string {
  const request: ProjectRenameRequest = {};
  if (name !== current) {
    if (name.trim() === '' || name.length > LIMITS.nameMax) {
      return `A name is 1 to ${String(LIMITS.nameMax)} characters.`;
    }
    request.name = name;
  }
  if (alias !== '') {
    const problem = aliasProblem(alias);
    if (problem !== null) {
      return problem;
    }
    request.alias = alias;
  }
  return Object.keys(request).length === 0
    ? 'Change the name or add an alias.'
    : request;
}

function RenameForm({ prefix, onDone, onCancel }: RenameFormProps) {
  const projects = useProjects();
  const rename = useRenameProject(prefix);
  const current =
    projects.data?.projects.find((p) => p.key_prefix === prefix)?.name ?? prefix;
  const [name, setName] = useState(current);
  const [alias, setAlias] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    nameRef.current?.focus();
  }, []);
  const submit = (event: SubmitEvent) => {
    event.preventDefault();
    const request = renameRequest(current, name, alias);
    if (typeof request === 'string') {
      setProblem(request);
      return;
    }
    setProblem(null);
    rename.mutate(request, {
      onSuccess: (info) => {
        onDone(`Project ${info.key_prefix} is now "${info.name}".`);
      },
    });
  };
  return (
    <form
      className="write-form rename-form"
      aria-label="Rename project"
      onSubmit={submit}
    >
      <label className="field">
        <span>Name</span>
        <input
          ref={nameRef}
          type="text"
          value={name}
          maxLength={LIMITS.nameMax}
          onChange={(event) => {
            setName(event.target.value);
          }}
        />
      </label>
      <label className="field">
        <span>New alias (optional)</span>
        <input
          type="text"
          value={alias}
          maxLength={32}
          onChange={(event) => {
            setAlias(event.target.value);
          }}
        />
      </label>
      {problem !== null && (
        <p role="alert" className="write-error">
          {problem}
        </p>
      )}
      <WriteError error={rename.error} />
      <div className="form-actions">
        <button type="submit" disabled={rename.isPending}>
          Save
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
