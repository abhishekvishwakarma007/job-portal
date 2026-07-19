import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import './styles.css'

const container = document.getElementById('root')

// Throwing beats a non-null assertion: if the template ever loses this element
// the failure names the cause instead of surfacing as "Cannot read properties
// of null" from inside React.
if (!container) {
  throw new Error('Root element #root is missing from index.html')
}

createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
