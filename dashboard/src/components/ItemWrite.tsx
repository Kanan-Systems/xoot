// The drawer's write controls for one item: Edit, then the writes the
// hierarchy allows on it (add the child kind, capture backlog, move a batch
// or subtask, record a decision). Each opens inline; a result is announced.
import { useState } from 'react';

import type { ItemView } from '../api/types.gen.ts';
import { childKindOf, isDecisionOwner, isMovable } from '../lib/itemRules.ts';
import { CaptureForm, CreateItemForm } from './CreateForms.tsx';
import { DecisionForm } from './DecisionForms.tsx';
import { Disclosure } from './Disclosure.tsx';
import { ItemEditor } from './ItemEditor.tsx';
import { MoveForm } from './MoveForm.tsx';

export function ItemWrite({ prefix, view }: { prefix: string; view: ItemView }) {
  const { item } = view;
  const [editing, setEditing] = useState(false);
  const [notice, setNotice] = useState('');
  const child = childKindOf(item.kind);
  const finish = (close: () => void) => (message: string) => {
    close();
    setNotice(message);
  };
  return (
    <section className="item-write" aria-label="Change this item">
      <p role="status" className="notice">
        {notice}
      </p>
      {editing ? (
        <ItemEditor
          prefix={prefix}
          view={view}
          onClose={() => {
            setEditing(false);
          }}
          onSaved={(message) => {
            setEditing(false);
            setNotice(message);
          }}
        />
      ) : (
        <>
          <button
            type="button"
            className="action"
            onClick={() => {
              setNotice('');
              setEditing(true);
            }}
          >
            Edit
          </button>
          {child !== null && (
            <Disclosure label={`Add ${child}`}>
              {(close) => (
                <CreateItemForm
                  prefix={prefix}
                  kind={child}
                  parent={item.key}
                  onDone={finish(close)}
                  onCancel={close}
                />
              )}
            </Disclosure>
          )}
          <Disclosure label="Capture backlog item">
            {(close) => (
              <CaptureForm
                prefix={prefix}
                foundOn={item.key}
                onDone={finish(close)}
                onCancel={close}
              />
            )}
          </Disclosure>
          {isMovable(item.kind) && (
            <Disclosure label="Move to…">
              {(close) => (
                <MoveForm
                  prefix={prefix}
                  item={item}
                  onDone={finish(close)}
                  onCancel={close}
                />
              )}
            </Disclosure>
          )}
          {isDecisionOwner(item.kind) && (
            <Disclosure label="Record decision">
              {(close) => (
                <DecisionForm
                  prefix={prefix}
                  owner={item.key}
                  onDone={finish(close)}
                  onCancel={close}
                />
              )}
            </Disclosure>
          )}
        </>
      )}
    </section>
  );
}
