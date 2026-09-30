// Input limits of the write requests, as schema.json states them (a test
// keeps them equal). Forms use them to refuse early; the server still checks.
export const LIMITS = {
  titleMin: 1,
  titleMax: 200,
  bodyMax: 32768,
  keyMax: 160,
  nameMax: 200,
} as const;

export const STATE_PATTERN = '^[a-z][a-z0-9_-]{0,31}$';
export const ALIAS_PATTERN = '^[a-z][a-z0-9-]{1,31}$';

// Why a title cannot be sent, or null when it can.
export function titleProblem(title: string): string | null {
  if (title.trim().length < LIMITS.titleMin) {
    return 'A title is required.';
  }
  if (title.length > LIMITS.titleMax) {
    return `A title is at most ${String(LIMITS.titleMax)} characters.`;
  }
  return null;
}

export function bodyProblem(body: string): string | null {
  return body.length > LIMITS.bodyMax
    ? `A body is at most ${String(LIMITS.bodyMax)} characters.`
    : null;
}

export function aliasProblem(alias: string): string | null {
  return new RegExp(ALIAS_PATTERN).test(alias)
    ? null
    : 'An alias is 2 to 32 characters: a lowercase letter, then letters, digits or dashes.';
}
