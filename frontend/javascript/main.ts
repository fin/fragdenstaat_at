import '../styles/main.scss'
import 'froide/frontend/javascript/main.ts'
import './misc.ts'
import * as Sentry from '@sentry/browser'


if (document.body.dataset.raven) {
  Sentry.init({
    dsn: document.body.dataset.raven
  })
}
