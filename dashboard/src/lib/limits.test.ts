import { describe, expect, it } from 'vitest';

import schema from '../api/schema.json';
import {
  ALIAS_PATTERN,
  aliasProblem,
  bodyProblem,
  LIMITS,
  STATE_PATTERN,
  titleProblem,
} from './limits.ts';

type Property = Record<string, unknown> & { anyOf?: Record<string, unknown>[] };

// A property's constraint, whether stated directly or in its string branch.
function constraint(model: string, field: string, name: string): unknown {
  const defs = schema.$defs as unknown as Record<
    string,
    { properties: Record<string, Property> }
  >;
  const property = defs[model]?.properties[field];
  if (property === undefined) {
    throw new Error(`${model}.${field} is not in the schema`);
  }
  if (name in property) {
    return property[name];
  }
  return property.anyOf?.find((branch) => name in branch)?.[name];
}

describe('write limits', () => {
  it('equal the schema', () => {
    for (const model of [
      'ItemCreateRequest',
      'CaptureRequest',
      'DecisionCreateRequest',
    ]) {
      expect(constraint(model, 'title', 'minLength')).toBe(LIMITS.titleMin);
      expect(constraint(model, 'title', 'maxLength')).toBe(LIMITS.titleMax);
      expect(constraint(model, 'body', 'maxLength')).toBe(LIMITS.bodyMax);
    }
    expect(constraint('ItemUpdateRequest', 'title', 'maxLength')).toBe(LIMITS.titleMax);
    expect(constraint('DecisionUpdateRequest', 'body', 'maxLength')).toBe(
      LIMITS.bodyMax,
    );
    expect(constraint('MoveRequest', 'key', 'maxLength')).toBe(LIMITS.keyMax);
    expect(constraint('MoveRequest', 'parent', 'maxLength')).toBe(LIMITS.keyMax);
    expect(constraint('CoverRequest', 'batch', 'maxLength')).toBe(LIMITS.keyMax);
    expect(constraint('ProjectRenameRequest', 'name', 'maxLength')).toBe(
      LIMITS.nameMax,
    );
    expect(constraint('ItemUpdateRequest', 'state', 'pattern')).toBe(STATE_PATTERN);
    expect(constraint('ProjectRenameRequest', 'alias', 'pattern')).toBe(ALIAS_PATTERN);
  });

  it('explain what cannot be sent', () => {
    expect(titleProblem('  ')).toBe('A title is required.');
    expect(titleProblem('x'.repeat(LIMITS.titleMax + 1))).toMatch(/at most 200/);
    expect(titleProblem('fine')).toBeNull();
    expect(bodyProblem('x'.repeat(LIMITS.bodyMax + 1))).toMatch(/at most 32768/);
    expect(bodyProblem('')).toBeNull();
    expect(aliasProblem('ok-alias')).toBeNull();
    expect(aliasProblem('Bad')).not.toBeNull();
    expect(aliasProblem('a')).not.toBeNull();
  });
});
