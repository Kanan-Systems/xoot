// A refused write: the server's message, a short summary of its details,
// and the open children that blocked it, if any. Rendered as text only.
import { ApiError } from '../api/client.ts';
import { detailLines, headline, openKeys } from '../lib/writeErrors.ts';
import { KeyTag } from './Titled.tsx';

export function WriteError({ error }: { error: unknown }) {
  if (error === null || error === undefined) {
    return null;
  }
  const details = error instanceof ApiError ? error.details : {};
  const lines = detailLines(details);
  const open = openKeys(details);
  return (
    <div role="alert" className="write-error">
      <p>{headline(error)}</p>
      {lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
      {open.length > 0 && (
        <>
          <p>Still open:</p>
          <ul className="list">
            {open.map((key) => (
              <li key={key}>
                <KeyTag value={key} />
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
