// What a node can ask of the canvas; nodes get it through context because
// React Flow renders them itself.
import { createContext, useContext } from 'react';

export interface NodeActions {
  open: (key: string) => void;
  showDone: () => void;
}

const noop = (): void => undefined;

export const NodeActionsContext = createContext<NodeActions>({
  open: noop,
  showDone: noop,
});

export function useNodeActions(): NodeActions {
  return useContext(NodeActionsContext);
}
