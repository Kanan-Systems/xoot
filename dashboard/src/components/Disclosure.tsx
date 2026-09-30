// A button that shows or hides one panel, as the other collapsible parts of
// the dashboard do; the panel's content gets a way to close it.
import { useId, useState, type ReactNode } from 'react';

interface DisclosureProps {
  label: string;
  children: (close: () => void) => ReactNode;
}

export function Disclosure({ label, children }: DisclosureProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div className="disclosure">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          setOpen(!open);
        }}
      >
        <span aria-hidden="true">{open ? '▾' : '▸'}</span> {label}
      </button>
      {open && (
        <div id={panelId} className="disclosure-panel">
          {children(() => {
            setOpen(false);
          })}
        </div>
      )}
    </div>
  );
}
