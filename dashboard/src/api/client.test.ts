import { afterEach, describe, expect, it, vi } from 'vitest';

import { mockApi, reply, requests, writeError } from '../test/api.ts';
import { ApiError, getJson, sendJson } from './client.ts';

afterEach(() => {
  vi.unstubAllGlobals();
});

async function caught(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof ApiError) {
      return error;
    }
  }
  throw new Error('expected an ApiError');
}

describe('sendJson', () => {
  it('sends the method, a JSON body, its content type and the cookie', async () => {
    const fetchMock = mockApi({ 'PATCH /projects/x/items/goal-1': { ok: true } });
    const result = await sendJson('PATCH', '/projects/x/items/goal-1', { title: 't' });
    expect(result).toEqual({ ok: true });
    const [sent] = requests(fetchMock, 'PATCH');
    expect(sent?.body).toEqual({ title: 't' });
    expect(sent?.headers['content-type']).toBe('application/json');
    expect(sent?.headers.accept).toBe('application/json');
    expect(sent?.credentials).toBe('same-origin');
  });

  it('keeps the details of a write error', async () => {
    mockApi({
      'POST /projects/x/moves': writeError(409, 'VersionConflictError', 'stale', {
        current_version: 3,
      }),
    });
    const error = await caught(sendJson('POST', '/projects/x/moves', {}));
    expect(error.status).toBe(409);
    expect(error.error).toBe('VersionConflictError');
    expect(error.message).toBe('stale');
    expect(error.details).toEqual({ current_version: 3 });
  });

  it('tolerates a guard refusal without details', async () => {
    mockApi({
      'POST /projects/x/moves': reply(405, {
        error: 'MethodNotAllowed',
        message: 'no',
      }),
    });
    const error = await caught(sendJson('POST', '/projects/x/moves', {}));
    expect(error.error).toBe('MethodNotAllowed');
    expect(error.details).toEqual({});
  });

  it('tolerates details that are not an object', async () => {
    mockApi({
      'POST /projects/x/moves': reply(400, { error: 'E', message: 'm', details: [1] }),
    });
    expect((await caught(sendJson('POST', '/projects/x/moves', {}))).details).toEqual(
      {},
    );
  });

  it('survives a body that is not JSON', async () => {
    mockApi({ 'POST /projects/x/moves': reply(502, '<html>bad gateway</html>') });
    const error = await caught(sendJson('POST', '/projects/x/moves', {}));
    expect(error.status).toBe(502);
    expect(error.error).toBe('HttpError');
  });
});

describe('getJson', () => {
  it('still reads with GET and gives read errors empty details', async () => {
    mockApi({});
    const error = await caught(getJson('/projects/x/tree'));
    expect(error.status).toBe(404);
    expect(error.details).toEqual({});
  });
});
