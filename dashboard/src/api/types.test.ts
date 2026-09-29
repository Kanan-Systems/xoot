// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { generateTypes } from '../../scripts/generate-types.mjs';
import schema from './schema.json?raw';
import committed from './types.gen.ts?raw';

describe('generated API types', () => {
  it('match a fresh generation from schema.json', async () => {
    expect(await generateTypes(schema), 'run: npm run gen:types').toBe(committed);
  });
});
