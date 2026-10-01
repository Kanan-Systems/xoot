// Moving by drag in the tree: the arming state machine, the confirmation in
// plain words that every drag-initiated move shows before anything is sent,
// then the move itself. A childless move is sent once confirmed, as the
// single request the server applies directly. A move with children returns
// the server's plan; when that plan moves exactly the items (by key, not by
// count) that were under it at the drop, it is applied without asking
// again, otherwise it is shown.
import { useEffect, useReducer } from 'react';

import type { ItemSummary, TreeEntry, MoveRequest } from '../api/types.gen.ts';
import { movedMessage, useMoveFlow } from '../hooks/useMoveFlow.ts';
import type { TwoPhase } from '../hooks/useTwoPhase.ts';
import {
  dragReducer,
  IDLE,
  sameKeys,
  subtreeKeys,
  type DragState,
} from '../lib/dragMachine.ts';
import { moveJourney } from '../lib/journey.ts';
import type { Titles } from '../lib/titles.ts';
import {
  descendants,
  moveFactsFromPlan,
  movePlanText,
  type MoveFacts,
} from '../lib/wording.ts';
import { ConfirmPanel, PlanConfirm } from './PlanConfirm.tsx';

export interface TreeMove {
  state: DragState;
  move: TwoPhase<MoveRequest>;
  arm: (item: ItemSummary) => void;
  disarm: () => void;
  drop: (item: ItemSummary, parent: string) => void;
  confirm: () => void;
  cancel: () => void;
}

function facts(
  item: ItemSummary,
  parent: string,
  entries: readonly TreeEntry[],
): MoveFacts {
  return {
    key: item.key,
    parent,
    newKey: null,
    children: descendants(item.key, entries),
  };
}

export function useTreeMove(
  prefix: string,
  entries: readonly TreeEntry[],
  titles: Titles,
  onNotice: (message: string) => void,
): TreeMove {
  const [state, dispatch] = useReducer(dragReducer, IDLE);
  const move = useMoveFlow(prefix, (output, request) => {
    onNotice(movedMessage(output, request, titles));
  });
  const armed = state.armed !== null;
  useEffect(() => {
    if (!armed) {
      return undefined;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        dispatch({ type: 'disarm' });
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [armed]);
  return {
    state,
    move,
    arm: (item) => {
      onNotice('');
      dispatch({ type: 'arm', item });
    },
    disarm: () => {
      dispatch({ type: 'disarm' });
    },
    drop: (item, parent) => {
      // One move at a time: a drop while another is sent snaps back.
      dispatch(
        move.flow.step === 'idle'
          ? { type: 'drop', item, parent, keys: subtreeKeys(item.key, entries) }
          : { type: 'cancel' },
      );
    },
    confirm: () => {
      const { pending } = state;
      if (pending === null) {
        return;
      }
      dispatch({ type: 'confirm' });
      const { item, parent, keys } = pending;
      void move.start(
        { key: item.key, parent, expected_version: item.version },
        { autoConfirm: (plan) => sameKeys(plan.changes, keys) },
      );
    },
    cancel: () => {
      dispatch({ type: 'cancel' });
    },
  };
}

interface TreeMovePanelProps {
  tree: TreeMove;
  entries: readonly TreeEntry[];
  titles: Titles;
}

export function TreeMovePanel({ tree, entries, titles }: TreeMovePanelProps) {
  const { pending } = tree.state;
  const { flow } = tree.move;
  return (
    <div className="plan-confirm" aria-live="polite">
      {pending !== null && (
        <ConfirmPanel
          title={`Move ${pending.item.key}`}
          summary={
            movePlanText(facts(pending.item, pending.parent, entries), titles) ??
            `Move ${pending.item.key} to ${pending.parent}?`
          }
          journey={moveJourney(pending.item.key, pending.parent, titles)}
          onConfirm={tree.confirm}
          onCancel={tree.cancel}
        />
      )}
      {pending === null && flow.step !== 'idle' && (
        <PlanConfirm
          title={`Move ${flow.request.key}`}
          flow={flow}
          summarize={(plan) =>
            movePlanText(
              moveFactsFromPlan(flow.request.key, flow.request.parent, plan),
              titles,
            )
          }
          journey={() => moveJourney(flow.request.key, flow.request.parent, titles)}
          onConfirm={() => void tree.move.confirm()}
          onCancel={tree.move.cancel}
        />
      )}
    </div>
  );
}
