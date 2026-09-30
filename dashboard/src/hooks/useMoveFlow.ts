// Moving a batch or subtask to a new parent, shared by the tree's drop and
// the drawer's picker: POST /moves with the version the move was read at;
// an item with children (or one that gained them) is confirmed first.
import { useMoveItem } from '../api/mutations.ts';
import type { ItemUpdateOutput, MoveRequest } from '../api/types.gen.ts';
import type { Titles } from '../lib/titles.ts';
import { moveFactsFromPlan, moveResultText } from '../lib/wording.ts';
import { useTwoPhase, type TwoPhase } from './useTwoPhase.ts';

// The result in plain words when the titles are known, else by key.
export function movedMessage(
  output: ItemUpdateOutput,
  request: MoveRequest,
  titles: Titles,
): string {
  const facts =
    output.plan === null
      ? { key: request.key, parent: request.parent, newKey: null, children: {} }
      : moveFactsFromPlan(request.key, request.parent, output.plan);
  const plain = moveResultText(facts, titles);
  if (plain !== null) {
    return plain;
  }
  return facts.newKey === null
    ? `Moved ${request.key} to ${request.parent}.`
    : `Moved ${request.key} to ${request.parent}: it is now ${facts.newKey}.`;
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
