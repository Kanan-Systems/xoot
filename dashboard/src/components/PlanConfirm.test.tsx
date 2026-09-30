import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/client.ts';
import type { ItemUpdateOutput } from '../api/types.gen.ts';
import { RESTARTED, useTwoPhase, type Send } from '../hooks/useTwoPhase.ts';
import { previewed, updated } from '../test/writes.ts';
import { PlanConfirm } from './PlanConfirm.tsx';

interface Req {
  key: string;
}

function Harness({
  send,
  onApplied,
}: {
  send: Send<Req, ItemUpdateOutput>;
  onApplied: (result: ItemUpdateOutput) => void;
}) {
  const flow = useTwoPhase(send, onApplied);
  return (
    <>
      <button type="button" onClick={() => void flow.start({ key: 'goal-1/batch-2' })}>
        Go
      </button>
      <PlanConfirm
        title="Move goal-1/batch-2"
        flow={flow.flow}
        onConfirm={() => void flow.confirm()}
        onCancel={flow.cancel}
      />
    </>
  );
}

const conflict = (error: string) => new ApiError(409, error, `${error} message`);

function setup(send: Send<Req, ItemUpdateOutput>) {
  const onApplied = vi.fn();
  render(<Harness send={send} onApplied={onApplied} />);
  fireEvent.click(screen.getByRole('button', { name: 'Go' }));
  return onApplied;
}

describe('PlanConfirm', () => {
  it('applies at once when the server needs no preview', async () => {
    const send = vi
      .fn<Send<Req, ItemUpdateOutput>>()
      .mockResolvedValue(updated('goal-2/batch-2', 'reparent'));
    const onApplied = setup(send);
    await waitFor(() => {
      expect(onApplied).toHaveBeenCalledTimes(1);
    });
    expect(send).toHaveBeenCalledWith({ key: 'goal-1/batch-2' }, null);
    expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull();
  });

  it('lists the plan, then resends the same request with the token', async () => {
    const send = vi
      .fn<Send<Req, ItemUpdateOutput>>()
      .mockResolvedValueOnce(previewed('reparent'))
      .mockResolvedValueOnce(updated('goal-2/batch-2', 'reparent'));
    const onApplied = setup(send);
    const region = await screen.findByRole('region', { name: /Confirm: Move/ });
    expect(region).toHaveTextContent('this changes 1 item');
    expect(region).toHaveTextContent(
      'goal-1/batch-2: key goal-1/batch-2 → goal-2/batch-2; parent goal-1 → goal-2',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    await waitFor(() => {
      expect(onApplied).toHaveBeenCalledTimes(1);
    });
    expect(send).toHaveBeenLastCalledWith({ key: 'goal-1/batch-2' }, 'tok-1');
  });

  it('starts over with a fresh preview when the token was spent or expired', async () => {
    const send = vi
      .fn<Send<Req, ItemUpdateOutput>>()
      .mockResolvedValueOnce(previewed('reparent', 'tok-1'))
      .mockRejectedValueOnce(conflict('ConfirmTokenError'))
      .mockResolvedValueOnce(previewed('reparent', 'tok-2'));
    const onApplied = setup(send);
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }));
    expect(await screen.findByText(RESTARTED)).toBeInTheDocument();
    expect(send).toHaveBeenCalledTimes(3);
    expect(send).toHaveBeenLastCalledWith({ key: 'goal-1/batch-2' }, null);
    expect(onApplied).not.toHaveBeenCalled();
  });

  it('previews when the item gained children before a direct write', async () => {
    const send = vi
      .fn<Send<Req, ItemUpdateOutput>>()
      .mockRejectedValueOnce(conflict('PreviewRequired'))
      .mockResolvedValueOnce(previewed('reparent'));
    setup(send);
    expect(await screen.findByText(RESTARTED)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeEnabled();
  });

  it('stops after one restart instead of looping', async () => {
    const send = vi
      .fn<Send<Req, ItemUpdateOutput>>()
      .mockRejectedValue(conflict('PreviewRequired'));
    setup(send);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'PreviewRequired message',
    );
    expect(send).toHaveBeenCalledTimes(2);
  });

  it('shows any other refusal and lets it be dismissed', async () => {
    const send = vi
      .fn<Send<Req, ItemUpdateOutput>>()
      .mockRejectedValue(new ApiError(422, 'HierarchyError', 'a batch needs a goal'));
    setup(send);
    expect(await screen.findByRole('alert')).toHaveTextContent('a batch needs a goal');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('cancels a preview without sending', async () => {
    const send = vi
      .fn<Send<Req, ItemUpdateOutput>>()
      .mockResolvedValue(previewed('drop'));
    setup(send);
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull();
    expect(send).toHaveBeenCalledTimes(1);
  });
});
