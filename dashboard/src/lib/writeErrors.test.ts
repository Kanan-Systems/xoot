import { describe, expect, it } from 'vitest';

import { ApiError } from '../api/client.ts';
import { CONFLICT_DETAILS } from '../test/writes.ts';
import { detailLines, headline, isRestart, openKeys } from './writeErrors.ts';

describe('write errors', () => {
  it('summarise a version conflict: fields, actors, current version', () => {
    expect(detailLines(CONFLICT_DETAILS)).toEqual([
      'Changed meanwhile: title, state.',
      'Changed by: claude/code.',
      'It is now at version 3; cancel to see it, then edit again.',
    ]);
  });

  it('summarise a plan over the cap', () => {
    expect(detailLines({ key: 'goal-1', size: 900, cap: 500 })).toEqual([
      'The change touches 900 items; the limit is 500.',
    ]);
  });

  it('ignore details of the wrong shape', () => {
    expect(
      detailLines({ changed_fields: 'title', actors: [null, 3, { kind: 1 }] }),
    ).toEqual([]);
    expect(openKeys({ open_keys: ['a', 2, 'b'] })).toEqual(['a', 'b']);
    expect(openKeys({})).toEqual([]);
  });

  it('restart only a token or plan that no longer holds', () => {
    expect(isRestart(new ApiError(409, 'PreviewRequired', 'm'))).toBe(true);
    expect(isRestart(new ApiError(409, 'ConfirmTokenError', 'm'))).toBe(true);
    expect(isRestart(new ApiError(409, 'StaleWriteError', 'm'))).toBe(true);
    expect(isRestart(new ApiError(409, 'VersionConflictError', 'm'))).toBe(false);
    expect(isRestart(new ApiError(422, 'ConfirmTokenError', 'm'))).toBe(false);
    expect(isRestart(new Error('x'))).toBe(false);
  });

  it('headline the error', () => {
    expect(headline(new ApiError(401, 'Unauthorized', 'm'))).toMatch(/Not signed in/);
    expect(headline(new ApiError(413, 'PayloadTooLarge', 'm'))).toMatch(/too large/);
    expect(headline(new ApiError(422, 'HierarchyError', 'a batch needs a goal'))).toBe(
      'a batch needs a goal',
    );
    expect(headline(new TypeError('network'))).toBe('The change could not be sent.');
  });
});
