import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import App from './App.jsx'
import './styles/globals.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 4000 },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3500,
          style: {
            background: '#1a1d2e',
            color: '#e8eaf6',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '10px',
            fontSize: '14px',
          },
          success: { iconTheme: { primary: '#22c55e', secondary: '#fff' } },
          error:   { iconTheme: { primary: '#ef4444', secondary: '#fff' } },
        }}
      />
    </QueryClientProvider>
  </React.StrictMode>
)
