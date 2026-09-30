// A write that may need confirming: the first call either applies at once
// or returns a plan and a confirm_token; confirming resends the original
// request with the token. The request and token live here, in component
// state. A token or plan that no longer holds (PreviewRequired, a spent,
// expired or mismatched token, a changed plan) starts over with a fresh
// preview once; any other refusal stops the flow with its error.
import { useState } from 'react';

import type { SubtreeOutput } from '../api/types.gen.ts';
import { isRestart } from '../lib/writeErrors.ts';

export interface TwoPhaseResult {
  phase: 'preview' | 'applied';
  confirm_token: string | null;
  plan: SubtreeOutput | null;
}

export const RESTARTED =
  'The change no longer matched its preview, so here is a fresh one to review.';

export type Flow<Req> =
  | { step: 'idle' }
  | { step: 'sending'; request: Req }
  | {
      step: 'preview' | 'confirming';
      request: Req;
      token: string;
      plan: SubtreeOutput;
      notice: string | null;
    }
  | { step: 'failed'; request: Req; error: unknown };

export interface TwoPhase<Req> {
  flow: Flow<Req>;
  start: (request: Req) => Promise<void>;
  confirm: () => Promise<void>;
  cancel: () => void;
}

export type Send<Req, Res> = (request: Req, token: string | null) => Promise<Res>;

export function useTwoPhase<Req, Res extends TwoPhaseResult>(
  send: Send<Req, Res>,
  onApplied: (result: Res, request: Req) => void,
): TwoPhase<Req> {
  const [flow, setFlow] = useState<Flow<Req>>({ step: 'idle' });

  const settle = (request: Req, result: Res, notice: string | null) => {
    if (result.phase === 'preview' && result.confirm_token !== null && result.plan) {
      setFlow({
        step: 'preview',
        request,
        token: result.confirm_token,
        plan: result.plan,
        notice,
      });
      return;
    }
    setFlow({ step: 'idle' });
    onApplied(result, request);
  };

  const preview = async (request: Req, notice: string | null, retried: boolean) => {
    setFlow({ step: 'sending', request });
    try {
      settle(request, await send(request, null), notice);
    } catch (error) {
      if (!retried && isRestart(error)) {
        await preview(request, RESTARTED, true);
        return;
      }
      setFlow({ step: 'failed', request, error });
    }
  };

  const start = (request: Req) => preview(request, null, false);

  const confirm = async () => {
    if (flow.step !== 'preview') {
      return;
    }
    const { request, token } = flow;
    setFlow({ ...flow, step: 'confirming', notice: null });
    try {
      settle(request, await send(request, token), null);
    } catch (error) {
      if (isRestart(error)) {
        await preview(request, RESTARTED, true);
        return;
      }
      setFlow({ step: 'failed', request, error });
    }
  };

  const cancel = () => {
    setFlow({ step: 'idle' });
  };

  return { flow, start, confirm, cancel };
}
