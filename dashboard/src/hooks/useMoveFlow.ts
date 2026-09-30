// Moving a batch or subtask to a new parent, shared by the tree's drop and
// the drawer's picker: POST /moves with the version the move was read at;
// an item with children (or one that gained them) is confirmed first.
import { useMoveItem } from '../api/mutations.ts';
import type { ItemUpdateOutput, MoveRequest } from '../api/types.gen.ts';
import { useTwoPhase, type TwoPhase } from './useTwoPhase.ts';

export function movedMessage(output: ItemUpdateOutput, request: MoveRequest): string {
  const moved = output.plan?.changes.find((change) => change.key === request.key);
  const newKey = moved?.after.key;
  return typeof newKey === 'string'
    ? `Moved ${request.key} to ${request.parent}: it is now ${newKey}.`
    : `Moved ${request.key} to ${request.parent}.`;
}

export function useMoveFlow(
  prefix: string,
  onMoved: (output: ItemUpdateOutput, request: MoveRequest) => void,
): TwoPhase<MoveRequest> {
  const move = useMoveItem(prefix);
  return useTwoPhase(
    (request: MoveRequest, token: string | null) =>
      move.mutateAsync(token === null ? request : { ...request, confirm_token: token }),
    onMoved,
  );
}
