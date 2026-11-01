import { App } from './App';
import * as React from 'react';
import { createRoot } from 'react-dom/client';

import './styles.css';

const container = document.getElementById('root');

if (!container) throw new Error('The #root element is missing.');

createRoot(container).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
