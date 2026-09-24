import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import ErrorBoundary from './components/layout/ErrorBoundary.jsx'
import './styles/tokens.css'
import './styles/base.css'
import './styles/chat.css'
import './styles/products.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
