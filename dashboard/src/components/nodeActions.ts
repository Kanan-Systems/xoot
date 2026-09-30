// What a node's inner buttons can ask of the canvas; nodes get it through
// context because React Flow renders them itself. Opening an item is the
// node click itself (TreeCanvas's onNodeClick), not an inner button.
import { createContext, useContext } from 'react';

export interface NodeActions {
  focus: (key: string) => void;
  showDone: () => void;
  toggle: (key: string) => void;
}

const noop = (): void => undefined;

export const NodeActionsContext = createContext<NodeActions>({
  focus: noop,
  showDone: noop,
  toggle: noop,
});

export function useNodeActions(): NodeActions {
  return useContext(NodeActionsContext);
}
