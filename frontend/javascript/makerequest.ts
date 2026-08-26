import 'froide/frontend/javascript/makerequest.js'
import store from 'froide/frontend/javascript/store'

/*
 * Keep the "sent by fax" notice in step with the chosen public bodies.
 *
 * The notice is rendered server-side by
 * foirequest/snippets/fax_delivery_notice.html, but the chooser is a Vue app
 * that re-renders no template, so without this the notice stayed as rendered
 * and went on describing bodies that were no longer selected.
 *
 * The source of truth is froide's Vuex store, not the DOM. store/index.js does
 * `export default createStore(...)`, a module singleton, and this entry imports
 * froide's makerequest.js, so the bundler resolves both to the same instance.
 * An earlier version read input[name="publicbody"] instead and had to cope with
 * the selection appearing as radios during search and as a hidden input once
 * committed, plus a MutationObserver because that swap fires no event. The
 * store just says which bodies are selected.
 *
 * Scopes are keyed 'make-request' or 'make-request-draft-<id>', so every scope
 * is read rather than naming one.
 *
 * Deliberately no eager first run: the server already rendered the correct
 * state for a preselected body, and the store may not have hydrated yet at
 * mount. Reacting only to real changes avoids hiding a correct notice.
 *
 * Wording is chosen here because it depends on how many bodies are selected and
 * how many are diverted, which is only known at runtime. The variants come from
 * data attributes so gettext still sees them.
 */
const NOTICE_ID = 'fds-fax-delivery-notice'

interface SelectedPublicBody {
  id: number | string
}

const notice = document.getElementById(NOTICE_ID)

if (notice !== null) {
  const faxIds = new Set(
    (notice.dataset.faxPublicbodyIds ?? '')
      .split(',')
      .map((id) => id.trim())
      .filter((id) => id !== '')
  )
  const heading = notice.querySelector<HTMLElement>('[data-fax-heading]')
  const message = notice.querySelector<HTMLElement>('[data-fax-message]')

  const selectedIds = (scoped: Record<string, SelectedPublicBody[]>): string[] =>
    Object.values(scoped ?? {})
      .flat()
      .map((pb) => String(pb?.id))
      .filter((id) => id !== 'undefined')

  const update = (scoped: Record<string, SelectedPublicBody[]>): void => {
    const selected = selectedIds(scoped)
    const diverted = selected.filter((id) => faxIds.has(id))

    if (diverted.length === 0) {
      notice.hidden = true
      return
    }

    const multiple = selected.length > 1
    const data = notice.dataset
    if (heading !== null) {
      heading.textContent =
        (multiple ? data.faxHeadingMultiple : data.faxHeadingSingle) ?? ''
    }
    if (message !== null) {
      const template =
        (multiple ? data.faxMessageMultiple : data.faxMessageSingle) ?? ''
      message.textContent = template
        .replace('{count}', String(diverted.length))
        .replace('{total}', String(selected.length))
    }
    notice.hidden = false
  }

  store.watch(
    (state: { scopedPublicBodies: Record<string, SelectedPublicBody[]> }) =>
      state.scopedPublicBodies,
    update,
    { deep: true }
  )
}
