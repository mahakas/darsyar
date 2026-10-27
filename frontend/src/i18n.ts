import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { ar } from './i18n/ar'
import { en } from './i18n/en'
import { fa } from './i18n/fa'

void i18n.use(initReactI18next).init({
  resources: { fa: { translation: fa }, en: { translation: en }, ar: { translation: ar } },
  lng: 'fa',
  fallbackLng: 'fa',
  interpolation: { escapeValue: false },
})

export default i18n
