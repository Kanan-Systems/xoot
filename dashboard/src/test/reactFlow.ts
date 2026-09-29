// jsdom lacks what React Flow measures with: ResizeObserver, DOMMatrix and
// element sizes. These stand-ins let the real <ReactFlow> render its nodes.
import { vi } from 'vitest';

class ResizeObserverStub {
  readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  // Reports each element once after the current render, as a browser does
  // after layout, so React Flow measures the node and shows it (it hides
  // nodes until measured).
  observe(target: Element): void {
    const contentRect = { width: 800, height: 600 } as DOMRectReadOnly;
    setTimeout(() => {
      this.callback([{ target, contentRect } as ResizeObserverEntry], this);
    }, 0);
  }

  unobserve(): void {
    // Nothing to stop.
  }

  disconnect(): void {
    // Nothing to stop.
  }
}

class DOMMatrixStub {
  readonly m22: number;

  constructor(transform?: string) {
    const scale = /scale\(([\d.]+)\)/.exec(transform ?? '');
    this.m22 = scale?.[1] === undefined ? 1 : Number(scale[1]);
  }
}

export function mockReactFlowDom(): void {
  vi.stubGlobal('ResizeObserver', ResizeObserverStub);
  vi.stubGlobal('DOMMatrixReadOnly', DOMMatrixStub);
  Object.defineProperties(HTMLElement.prototype, {
    offsetWidth: { configurable: true, get: () => 800 },
    offsetHeight: { configurable: true, get: () => 600 },
  });
}
