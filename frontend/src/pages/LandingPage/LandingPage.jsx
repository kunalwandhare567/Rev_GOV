import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Shield, Globe, Zap, ChevronRight } from 'lucide-react'
import useChatStore from '../../store/chatStore'
import { applicationsApi } from '../../api/applications'
import { t, LANGUAGE_NAMES } from '../../i18n'
import { SERVICE_IDS, SUPPORTED_LANGS } from '../../utils/constants'
import styles from './LandingPage.module.css'

const SERVICE_ICONS = {
  income_certificate:  '💰',
  caste_certificate:   '📜',
  obc_ncl_certificate: '🏷️',
  domicile_certificate:'🏠',
}

const HOW_STEPS = ['step1', 'step2', 'step3', 'step4', 'step5']

export default function LandingPage() {
  const { language, setLanguage } = useChatStore()
  const [count, setCount] = useState({ apps: 0, langs: 0, sla: 0, privacy: 0 })
  const statsRef = useRef(null)

  const { data: servicesData } = useQuery({
    queryKey: ['services'],
    queryFn: () => applicationsApi.listServices(),
  })

  useEffect(() => {
    const targets = { apps: 50000, langs: 3, sla: 3, privacy: 100 }
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      Object.entries(targets).forEach(([key, target]) => {
        let current = 0
        const step = target / 60
        const interval = setInterval(() => {
          current = Math.min(current + step, target)
          setCount(prev => ({ ...prev, [key]: Math.floor(current) }))
          if (current >= target) clearInterval(interval)
        }, 20)
      })
      observer.disconnect()
    })
    if (statsRef.current) observer.observe(statsRef.current)
    return () => observer.disconnect()
  }, [])

  const services = servicesData?.services || []

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroBg}>
          <span className={styles.orb1} /><span className={styles.orb2} /><span className={styles.orb3} />
        </div>
        <div className={styles.heroContent}>
          <div className={styles.langBar}>
            {SUPPORTED_LANGS.map(lang => (
              <button key={lang} className={`${styles.langChip} ${language === lang ? styles.langActive : ''}`}
                onClick={() => setLanguage(lang)}>
                {LANGUAGE_NAMES[lang]}
              </button>
            ))}
          </div>
          <h1 className={styles.heroHeadline}>
            {t(language, 'hero.headline')}<br />
            <span className={styles.heroAccent}>{t(language, 'hero.headlineAccent')}</span>
          </h1>
          <p className={styles.heroSubtitle}>{t(language, 'hero.subtitle')}</p>
          <div className={styles.heroCtas}>
            <Link to="/chat" className={styles.ctaPrimary}>
              {t(language, 'hero.cta_apply')} <ArrowRight size={18} />
            </Link>
            <Link to="/status" className={styles.ctaSecondary}>
              {t(language, 'hero.cta_track')}
            </Link>
          </div>
          <div className={styles.trustBar}>
            {['trust_1','trust_2','trust_3'].map(k => (
              <span key={k} className={styles.trustItem}><Shield size={14} /> {t(language, `hero.${k}`)}</span>
            ))}
          </div>
        </div>
        <div className={styles.heroChatPreview}>
          <div className={styles.chatPreview}>
            <div className={styles.previewBubble + ' ' + styles.assistant}>
              {language === 'hi' ? 'नमस्ते! आपको कौन सा प्रमाण पत्र चाहिए?' :
               language === 'mr' ? 'नमस्कार! कोणते प्रमाणपत्र हवे आहे?' :
               'Hello! Which certificate do you need?'}
            </div>
            <div className={styles.previewBubble + ' ' + styles.user}>
              {language === 'hi' ? 'आय प्रमाण पत्र' : language === 'mr' ? 'उत्पन्न प्रमाणपत्र' : 'Income Certificate'}
            </div>
            <div className={styles.previewBubble + ' ' + styles.assistant}>
              {language === 'hi' ? '✅ शुरू करते हैं! आपकी वार्षिक आय कितनी है?' :
               language === 'mr' ? '✅ सुरुवात करूया! तुमचे वार्षिक उत्पन्न किती आहे?' :
               '✅ Great! What is your annual income?'}
            </div>
            <div className={styles.typingRow}><span className={styles.dot}/><span className={styles.dot}/><span className={styles.dot}/></div>
          </div>
        </div>
      </section>

      <section className={styles.servicesSection}>
        <div className={styles.sectionInner}>
          <h2 className={styles.sectionTitle}>{t(language, 'services.title')}</h2>
          <p className={styles.sectionSubtitle}>{t(language, 'services.subtitle')}</p>
          <div className={styles.serviceCards}>
            {services.length > 0 ? services.map(svc => (
              <div key={svc.id} className={styles.serviceCard}>
                <div className={styles.serviceIcon}>{SERVICE_ICONS[svc.id] || '📄'}</div>
                <div className={styles.serviceInfo}>
                  <h3 className={styles.serviceName}>{t(language, `services.${svc.id.replace('_certificate','')}`)||svc.name_en}</h3>
                  <div className={styles.serviceMeta}>
                    <span className={styles.feeBadge}>
                      {svc.fee_amount === 0 ? t(language,'services.free') : `₹${svc.fee_amount}`}
                    </span>
                    <span className={styles.slaBadge}>{svc.sla_days} {t(language,'services.days')}</span>
                  </div>
                </div>
                <Link to={`/chat?service=${svc.id}`} className={styles.serviceApplyBtn}>
                  {t(language,'services.applyBtn')} <ChevronRight size={14} />
                </Link>
              </div>
            )) : [1,2,3,4].map(i => <div key={i} className={`${styles.serviceCard} skeleton`} style={{height:'90px'}} />)}
          </div>
        </div>
      </section>

      <section className={styles.howSection}>
        <div className={styles.sectionInner}>
          <h2 className={styles.sectionTitle}>{t(language,'howItWorks.title')}</h2>
          <div className={styles.steps}>
            {HOW_STEPS.map((step, i) => (
              <div key={step} className={styles.step}>
                <div className={styles.stepNumber}>{i + 1}</div>
                <h4 className={styles.stepTitle}>{t(language, `howItWorks.${step}_title`)}</h4>
                <p className={styles.stepDesc}>{t(language, `howItWorks.${step}_desc`)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.dataGuardSection}>
        <div className={styles.sectionInner + ' ' + styles.splitRow}>
          <div className={styles.splitText}>
            <div className={styles.badgePill}><Shield size={14}/> Data Guard Active</div>
            <h2 className={styles.splitHeadline}>Your Personal Data Never Leaves Our Servers</h2>
            <p className={styles.splitBody}>
              Every request is screened by our Trust Boundary Layer. Your Aadhaar, name and personal details are
              encrypted and verified locally — never sent to external cloud services.
            </p>
            <Link to="/admin/data-guard" className={styles.demoLink}>See it live →</Link>
          </div>
          <div className={styles.trustDiagram}>
            <div className={styles.zoneBox + ' ' + styles.zoneSecure}>
              <span className={styles.zoneDot + ' ' + styles.green}/>
              <b>On-Premise</b>
              <div className={styles.fieldList}>
                <span className={styles.blockedField}>🔴 aadhaar_number</span>
                <span className={styles.blockedField}>🔴 applicant_name</span>
                <span className={styles.blockedField}>🔴 date_of_birth</span>
              </div>
            </div>
            <div className={styles.blockArrow}>
              <span className={styles.arrowLine}/>
              <span className={styles.blockSign}>BLOCKED ✕</span>
            </div>
            <div className={styles.zoneBox + ' ' + styles.zoneCloud}>
              <span className={styles.zoneDot + ' ' + styles.gray}/>
              <b>Cloud LLM</b>
              <div className={styles.fieldList}>
                <span className={styles.safeField}>🟢 service_type</span>
                <span className={styles.safeField}>🟢 message_text</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.statsSection} ref={statsRef}>
        <div className={styles.sectionInner}>
          <div className={styles.statsGrid}>
            {[
              { label: 'Applications Processed', value: count.apps.toLocaleString() + '+', icon: '📋' },
              { label: 'Languages Supported',    value: count.langs,  icon: <Globe size={24}/> },
              { label: 'Avg SLA (Income)',       value: count.sla + ' days', icon: <Zap size={24}/> },
              { label: 'Data Privacy',           value: count.privacy + '%', icon: <Shield size={24}/> },
            ].map((stat, i) => (
              <div key={i} className={styles.statCard}>
                <div className={styles.statIcon}>{stat.icon}</div>
                <div className={styles.statValue}>{stat.value}</div>
                <div className={styles.statLabel}>{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── MULTI-CHANNEL SECTION ── */}
      <section className={styles.channelSection}>
        <div className={styles.sectionInner}>
          <h2 className={styles.sectionTitle}>
            {language === 'hi' ? 'जैसे चाहे वैसे आवेदन करें' :
             language === 'mr' ? 'तुमच्या पद्धतीने अर्ज करा' :
             'Apply Your Way — Any Channel, One Application'}
          </h2>
          <p className={styles.sectionSubtitle}>
            {language === 'hi' ? 'सभी चैनल एक ही DB साझा करते हैं — कभी भी स्विच करें।' :
             language === 'mr' ? 'सर्व चॅनेल एकच DB वापरतात — कधीही स्विच करा।' :
             'Start on WhatsApp, continue on Web, finish via Phone — all synced in real time.'}
          </p>
          <div className={styles.channelCards}>
            {[
              { href: '/whatsapp', icon: '💬', title: 'WhatsApp Chat', desc: language === 'hi' ? 'WhatsApp जैसी चैट से आवेदन करें' : 'Apply via WhatsApp-style chat with voice & documents', color: '#25d366', bg: 'rgba(37,211,102,0.08)' },
              { href: '/chat', icon: '🌐', title: 'Web Portal', desc: language === 'hi' ? 'वेब पोर्टल से आवेदन करें' : 'Full-featured citizen web portal with live form', color: '#6366f1', bg: 'rgba(99,102,241,0.08)' },
              { href: '/ivr', icon: '📞', title: 'Phone IVR', desc: language === 'hi' ? 'फोन से सेवाएं पाएं' : 'Dial our IVR helpline — voice + keypad navigation', color: '#f59e0b', bg: 'rgba(245,158,11,0.08)' },
              { href: '/status', icon: '🔍', title: 'Track Status', desc: language === 'hi' ? 'आवेदन की स्थिति जानें' : 'Track your application with a public tracking ID', color: '#22d3ee', bg: 'rgba(34,211,238,0.08)' },
            ].map(ch => (
              <a key={ch.href} href={ch.href} className={styles.channelCard} style={{ '--ch-color': ch.color, '--ch-bg': ch.bg }}>
                <div className={styles.channelCardIcon}>{ch.icon}</div>
                <div className={styles.channelCardTitle}>{ch.title}</div>
                <div className={styles.channelCardDesc}>{ch.desc}</div>
              </a>
            ))}
          </div>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.sectionInner}>
          <div className={styles.footerRow}>
            <div>
              <span className={styles.footerLogo}>🏛️ RevenueSeva</span>
              <p className={styles.footerTagline}>{t(language,'footer.tagline')}</p>
            </div>
            <div className={styles.footerLinks}>
              <Link to="/services">Services</Link>
              <Link to="/status">Track Application</Link>
              <a href="/whatsapp">💬 WhatsApp</a>
              <a href="/ivr">📞 IVR</a>
              <Link to="/admin/login">Admin</Link>
              <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API Docs</a>
            </div>
          </div>
          <div className={styles.footerBottom}>
            <span>{t(language,'footer.poweredBy')}</span>
            <span>{t(language,'footer.demoNote')}</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
