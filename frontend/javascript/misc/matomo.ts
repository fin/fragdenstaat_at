// NOTE: this is Open Knowledge Foundation *Deutschland*'s Matomo instance.
// AT's previous copy of this file additionally hardcoded setSiteId('25') and
// setDomains(['*.fragdenstaat.de']), i.e. DE's property -- enabling analytics
// would have reported AT traffic into DE's stats. The site id now comes from
// body[data-matomoid]. Confirm the host and the property before switching
// analytics on; see MERGE_PLAN.md 9.1 (MATOMO_SITE_ID).
const MATOMO_DOMAIN = 'https://traffic.okfn.de'

window._paq = window._paq ?? []
window._paq.push(['trackPageView'])
window._paq.push(['enableLinkTracking'])
window._paq.push(['setDomains', [document.location.host]])
window._paq.push(['setTrackerUrl', `${MATOMO_DOMAIN}/matomo.php`])
window._paq.push(['disableCookies'])
window._paq.push(['disableBrowserFeatureDetection'])

const matomoId = document.body.dataset.matomoid
if (matomoId && !document.body.dataset.dnt) {
  window._paq.push(['setSiteId', matomoId])
  const script = document.createElement('script')
  script.type = 'text/javascript'
  script.async = true
  script.defer = true
  script.src = `${MATOMO_DOMAIN}/matomo.js`
  document.body.appendChild(script)
}
