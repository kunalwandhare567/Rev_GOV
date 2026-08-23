import en from './en.json'
import hi from './hi.json'
import mr from './mr.json'

const translations = { en, hi, mr }

export function t(lang, key) {
  const keys = key.split('.')
  const dict = translations[lang] || translations['en']
  const fallback = translations['en']
  const resolve = (obj, k) => k.reduce((acc, k) => (acc && acc[k] !== undefined ? acc[k] : undefined), obj)
  return resolve(dict, keys) ?? resolve(fallback, keys) ?? key
}

export const SUPPORTED_LANGUAGES = ['en', 'hi', 'mr']
export const LANGUAGE_NAMES = { en: 'English', hi: 'हिन्दी', mr: 'मराठी' }
export default translations
