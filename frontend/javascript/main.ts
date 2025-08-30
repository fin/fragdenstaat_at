import '../styles/main.scss'

import 'froide/frontend/javascript/snippets/bootstrap'
import 'froide/frontend/javascript/snippets/copy-text'
import 'froide/frontend/javascript/snippets/form-ajax'
import 'froide/frontend/javascript/snippets/misc'
import 'froide/frontend/javascript/snippets/share-links'
import 'froide/frontend/javascript/snippets/inline-edit-forms'
import 'froide/frontend/javascript/snippets/color-mode'
// import { initSearch } from 'froide/frontend/javascript/snippets/search'

import './donation-form.ts'
import './drawer-menu.ts'
import './magnifier.ts'
import './misc.ts'
import './slider.js'
import './smooth-scroll.ts'
import './top-banner.ts'

if (document.body.dataset.sentry !== undefined) {
  void import('./sentry').then((mod) => {
    if (document.body.dataset.sentry !== undefined) {
      mod.init(document.body.dataset.sentry)
    }
  })
}