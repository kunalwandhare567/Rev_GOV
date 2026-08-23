import { create } from 'zustand'

const useUIStore = create((set) => ({
  sidebarOpen:  true,
  activeModal:  null,
  demoMode:     import.meta.env.VITE_DEMO_MODE === 'true',
  setSidebarOpen: (v)    => set({ sidebarOpen: v }),
  toggleSidebar:  ()     => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  openModal:      (name) => set({ activeModal: name }),
  closeModal:     ()     => set({ activeModal: null }),
  toggleDemoMode: ()     => set((s) => ({ demoMode: !s.demoMode })),
}))

export default useUIStore
