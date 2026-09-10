import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { CheckCircle2, XCircle, ShieldCheck, Download, Home, Lock, Award } from 'lucide-react'
import client from '../../api/client'
import styles from './CertificateVerifier.module.css'

export default function CertificateVerifier() {
  const { certNumber } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function fetchVerification() {
      try {
        setLoading(true)
        const res = await client.get(`/certificates/verify/${certNumber}`)
        setData(res.data || res)
      } catch (err) {
        setError(err.response?.data?.detail?.message || err.message || 'Verification failed')
      } finally {
        setLoading(false)
      }
    }
    if (certNumber) {
      fetchVerification()
    }
  }, [certNumber])

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.card} style={{ textAlign: 'center' }}>
          <div className={styles.loadingSpinner} />
          <h3 className={styles.title}>Verifying Certificate Authenticity...</h3>
          <p className={styles.subtitle}>Checking government registry cryptographic signatures</p>
        </div>
      </div>
    )
  }

  const isValid = data && data.valid

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.govEmblem}>🏛️</div>
          <h1 className={styles.title}>Government Revenue Department</h1>
          <p className={styles.subtitle}>Official Certificate Verification Portal</p>
          
          <div className={`${styles.badge} ${isValid ? styles.validBadge : styles.invalidBadge}`}>
            {isValid ? (
              <>
                <CheckCircle2 size={18} />
                <span>OFFICIALLY VERIFIED & AUTHENTIC</span>
              </>
            ) : (
              <>
                <XCircle size={18} />
                <span>UNVERIFIED / INVALID CERTIFICATE</span>
              </>
            )}
          </div>
        </div>

        {isValid ? (
          <>
            <div className={styles.detailsGrid}>
              <div className={styles.fieldItem}>
                <span className={styles.fieldLabel}>Certificate Number</span>
                <span className={styles.fieldVal}>{data.certificate_number}</span>
              </div>

              <div className={styles.fieldItem}>
                <span className={styles.fieldLabel}>Service Type</span>
                <span className={styles.fieldVal}>{data.service_name}</span>
              </div>

              <div className={styles.fieldItem}>
                <span className={styles.fieldLabel}>Tracking Identifier</span>
                <span className={styles.fieldVal}>{data.tracking_id || data.application_number}</span>
              </div>

              <div className={styles.fieldItem}>
                <span className={styles.fieldLabel}>Citizen Reference</span>
                <span className={styles.fieldVal}>{data.citizen_ref}</span>
              </div>

              <div className={styles.fieldItem}>
                <span className={styles.fieldLabel}>Issuing Authority</span>
                <span className={styles.fieldVal}>{data.issuing_authority}</span>
              </div>

              <div className={styles.fieldItem}>
                <span className={styles.fieldLabel}>Issue Date</span>
                <span className={styles.fieldVal}>
                  {data.issue_date ? new Date(data.issue_date).toLocaleDateString() : 'N/A'}
                </span>
              </div>
            </div>

            <div className={styles.hashBox}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', marginBottom: '0.375rem', color: '#94a3b8', fontWeight: 600 }}>
                <Lock size={14} /> Digital SHA-256 Stamp Digest:
              </div>
              <div>{data.full_hash || data.digital_stamp_hash}</div>
            </div>

            <div className={styles.actions}>
              {data.download_url && (
                <a
                  href={`${client.defaults.baseURL.replace('/api/v1', '')}${data.download_url}`}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.downloadBtn}
                >
                  <Download size={18} /> Download Verified Certificate
                </a>
              )}
              <Link to="/" className={styles.homeBtn}>
                <Home size={18} /> Portal Home
              </Link>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '1rem 0' }}>
            <p style={{ color: '#f87171', fontSize: '0.9375rem', marginBottom: '1.5rem' }}>
              {error || 'The certificate number scanned could not be verified in the authoritative government registry.'}
            </p>
            <Link to="/" className={styles.homeBtn}>
              <Home size={18} /> Return to Portal Home
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
