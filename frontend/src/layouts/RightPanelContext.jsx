import { createContext, useContext, useState, useCallback } from 'react'

const RightPanelContext = createContext(null)

/**
 * RightPanelProvider — wraps the CitizenDashboardLayout.
 * Each page (AssistantPage, MyApplicationsPage, DocumentsPage) can push
 * its own content into the right panel via useRightPanel().
 */
export function RightPanelProvider({ children }) {
  const [panelContent, setPanelContent] = useState(null)
  const [panelTitle,   setPanelTitle]   = useState('')

  const setRightPanel = useCallback((title, content) => {
    setPanelTitle(title)
    setPanelContent(content)
  }, [])

  const clearRightPanel = useCallback(() => {
    setPanelTitle('')
    setPanelContent(null)
  }, [])

  return (
    <RightPanelContext.Provider value={{ panelContent, panelTitle, setRightPanel, clearRightPanel }}>
      {children}
    </RightPanelContext.Provider>
  )
}

/**
 * useRightPanel — hook for pages to inject content into the layout's right panel.
 *
 * Usage:
 *   const { setRightPanel } = useRightPanel()
 *   useEffect(() => { setRightPanel('Activity', <ActivityPanel />) }, [])
 */
export function useRightPanel() {
  const ctx = useContext(RightPanelContext)
  if (!ctx) throw new Error('useRightPanel must be used inside RightPanelProvider')
  return ctx
}
