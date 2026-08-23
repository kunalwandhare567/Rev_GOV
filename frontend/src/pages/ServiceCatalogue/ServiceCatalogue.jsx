import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Search } from 'lucide-react'
import useChatStore from '../../store/chatStore'
import { applicationsApi } from '../../api/applications'
import { t } from '../../i18n'
import styles from './ServiceCatalogue.module.css'

const SERVICE_ICONS = {
  income_certificate:'💰', caste_certificate:'📜', obc_ncl_certificate:'🏷️', domicile_certificate:'🏠'
}

export default function ServiceCatalogue() {
  const { language } = useChatStore()
  const [filter, setFilter] = useState('all')
  const [searchQ, setSearchQ] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['services'],
    queryFn: () => applicationsApi.listServices(),
  })

  const services = (data?.services || []).filter(s => {
    const matchSearch = !searchQ || s.name_en.toLowerCase().includes(searchQ.toLowerCase())
    const matchFilter = filter === 'all' || s.id.includes(filter)
    return matchSearch && matchFilter
  })

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <h1 className={styles.title}>{t(language,'services.title')}</h1>
        <p className={styles.subtitle}>{t(language,'services.subtitle')}</p>
      </section>

      <div className={styles.inner}>
        <div className={styles.filterBar}>
          <div className={styles.searchInput}>
            <Search size={16} className={styles.searchIcon}/>
            <input className={styles.searchBox} value={searchQ} onChange={e=>setSearchQ(e.target.value)} placeholder={t(language,'common.search')+' services…'}/>
          </div>
          <div className={styles.filterChips}>
            {[['all','All'],['income','Income'],['caste','Caste'],['obc','OBC-NCL'],['domicile','Domicile']].map(([v,l]) => (
              <button key={v} className={`${styles.chip} ${filter===v?styles.chipActive:''}`} onClick={()=>setFilter(v)}>{l}</button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className={styles.grid}>{[1,2,3,4].map(i=><div key={i} className={`${styles.card} skeleton`} style={{height:'260px'}}/>)}</div>
        ) : (
          <div className={styles.grid}>
            {services.map(svc => (
              <div key={svc.id} className={styles.card}>
                <div className={styles.cardTop}>
                  <span className={styles.cardIcon}>{SERVICE_ICONS[svc.id]||'📄'}</span>
                  <div>
                    <h3 className={styles.cardName}>{svc.name_en}</h3>
                    {svc.name_hi && <p className={styles.cardNameLang}>{svc.name_hi}</p>}
                  </div>
                </div>
                <div className={styles.cardMeta}>
                  <div className={styles.metaItem}>
                    <span className={styles.metaKey}>{t(language,'services.fee')}</span>
                    <span className={styles.feePill}>{svc.fee_amount===0?t(language,'services.free'):`₹${svc.fee_amount}`}</span>
                  </div>
                  <div className={styles.metaItem}>
                    <span className={styles.metaKey}>{t(language,'services.sla')}</span>
                    <span className={styles.slaPill}>{svc.sla_days} {t(language,'services.days')}</span>
                  </div>
                  {svc.department && (
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>{t(language,'services.department')}</span>
                      <span className={styles.metaVal}>{svc.department}</span>
                    </div>
                  )}
                </div>
                {svc.required_documents?.length > 0 && (
                  <div className={styles.docList}>
                    <p className={styles.docListTitle}>{t(language,'services.required_docs')}:</p>
                    {svc.required_documents.map(d=>(
                      <span key={d} className={styles.docItem}>📄 {d.replace(/_/g,' ')}</span>
                    ))}
                  </div>
                )}
                <div className={styles.cardActions}>
                  <Link to={`/chat?service=${svc.id}`} className={styles.applyBtn}>
                    {t(language,'services.applyBtn')} <ChevronRight size={14}/>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
