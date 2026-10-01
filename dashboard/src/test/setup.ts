import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';

// A full-app render takes ~100ms alone but over 1s when every core runs a
// test worker (measured 1255ms), past the library's 1000ms default for
// findBy*/waitFor, which made route-level tests fail at random. The
// assertions are unchanged; only the time they may wait for data is.
configure({ asyncUtilTimeout: 5000 });
