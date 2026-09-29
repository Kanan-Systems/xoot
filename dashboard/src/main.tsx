import '@xyflow/react/dist/style.css';
import './styles/app.css';
import './styles/tree.css';
import './styles/views.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App, createQueryClient } from './App.tsx';

const root = document.getElementById('root');
if (root === null) {
  throw new Error('missing #root');
}
createRoot(root).render(
  <StrictMode>
    <App client={createQueryClient()} />
  </StrictMode>,
);
