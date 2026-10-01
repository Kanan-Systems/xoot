// A switch for failures only a real browser shows: with "drag" in
// localStorage['xoot:debug'], every drop logs what it saw and decided to the
// console. Nothing is logged otherwise, and nothing leaves the page.
import type { Decision } from './dropTarget.ts';
import type { DropScene } from './flowDrop.ts';

export const DEBUG_KEY = 'xoot:debug';

// Storage can be missing or throw (private windows, blocked site data).
export function debugging(topic: string): boolean {
  try {
    return (window.localStorage.getItem(DEBUG_KEY) ?? '').includes(topic);
  } catch {
    return false;
  }
}

export function logDrop(id: string, scene: DropScene, decision: Decision): void {
  if (!debugging('drag')) {
    return;
  }
  console.info('[xoot drag] drop', {
    dragged: { id, rect: scene.dragged.rect },
    pointer: { screen: scene.screen, flow: scene.pointer },
    viewport: scene.viewport,
    candidates: decision.judged,
    decision: decision.result,
    reason: decision.why,
  });
}
