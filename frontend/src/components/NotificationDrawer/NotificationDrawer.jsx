import { useState, useEffect } from 'react'
import { Smartphone, X, Bell } from 'lucide-react'
import useSSE from '../../hooks/useSSE'
import useChatStore from '../../store/chatStore'
import styles from './NotificationDrawer.module.css'

export default function NotificationDrawer() {
  const [isOpen, setIsOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)

  const citizenIdentifier = useChatStore((s) => s.citizenIdentifier)
  const applicationNumber = useChatStore((s) => s.applicationNumber)

  // Subscribe to real-time status updates via SSE
  const sseData = useSSE(applicationNumber || citizenIdentifier)

  useEffect(() => {
    if (!sseData) return

    const event = sseData.data || sseData
    const newStatus = event.new_status || event.status
    if (!newStatus) return

    const statusMessages = {
      SUBMITTED_FOR_VERIFICATION: '📋 Application submitted! Sent to government admin for review.',
      UNDER_REVIEW: '🔍 Admin is currently reviewing your uploaded documents.',
      APPROVED: '🎉 Great news! Your application documents have been VERIFIED & APPROVED by Admin.',
      PAYMENT_REQUIRED: '💳 Document Verification Complete! UPI QR Code Payment option is now unlocked.',
      PAYMENT_COMPLETED: '✅ Payment received & verified. Certificate generation started.',
      CERTIFICATE_READY: '📜 Certificate ready! Your verified government certificate has been issued.',
    }

    const text = statusMessages[newStatus] || `📌 Status update: Moved to ${newStatus}`

    const newNotif = {
      id: Date.now(),
      channel: 'WHATSAPP / SMS',
      sender: 'Revenue Seva (Govt of India)',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text,
    }

    setNotifications((prev) => [newNotif, ...prev])
    setUnreadCount((c) => c + 1)
  }, [sseData])

  const toggleDrawer = () => {
    setIsOpen(!isOpen)
    if (!isOpen) {
      setUnreadCount(0)
    }
  }

  return (
    <>
      <button className={styles.floatingTrigger} onClick={toggleDrawer} title="Live Mobile Notifications Simulator">
        <Smartphone size={18} />
        <span>Mobile Notifications</span>
        {unreadCount > 0 && <span className={styles.badge}>{unreadCount}</span>}
      </button>

      {isOpen && (
        <div className={styles.drawerOverlay}>
          <div className={styles.drawerHeader}>
            <div className={styles.drawerTitle}>
              <Bell size={16} style={{ color: '#10b981' }} />
              <span>Simulated Citizen Mobile Push</span>
            </div>
            <button className={styles.closeBtn} onClick={() => setIsOpen(false)}>
              <X size={16} />
            </button>
          </div>

          <div className={styles.notificationsList}>
            {notifications.length === 0 ? (
              <div className={styles.emptyState}>
                <Smartphone size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
                <p>No new notifications yet.</p>
                <p style={{ fontSize: '0.75rem', opacity: 0.7, marginTop: 4 }}>
                  Incoming WhatsApp & SMS status alerts will pop up here in real time as your application progresses.
                </p>
              </div>
            ) : (
              notifications.map((n) => (
                <div key={n.id} className={styles.notifBubble}>
                  <div className={styles.bubbleMeta}>
                    <span className={styles.senderName}>{n.sender}</span>
                    <span>{n.time}</span>
                  </div>
                  <div className={styles.bubbleBody}>{n.text}</div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </>
  )
}
