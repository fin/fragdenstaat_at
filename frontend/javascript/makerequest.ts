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

interface StoreState {
  scopedPublicBodies?: Record<string, SelectedPublicBody[]>
  scopedPublicBodiesMap?: Record<string, Record<string, boolean>>
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

  const selectedIds = (state: StoreState): string[] => {
    const ids = new Set<string>()
    // The list of selected bodies, per scope ('make-request', or
    // 'make-request-draft-<id>'). Read every scope rather than naming one.
    Object.values(state.scopedPublicBodies ?? {})
      .flat()
      .forEach((pb) => {
        if (pb?.id !== undefined && pb?.id !== null) {
          ids.add(String(pb.id))
        }
      })
    // ...and the id map beside it, because not every mutation keeps the two in
    // step. Numeric keys only: SET_PUBLICBODY_ID writes the literal string
    // 'publicBodyId' as a key (store/index.js, an upstream slip), which must
    // not be read as an id.
    Object.values(state.scopedPublicBodiesMap ?? {}).forEach((map) => {
      Object.entries(map ?? {}).forEach(([id, present]) => {
        if (present === true && /^\d+$/.test(id)) {
          ids.add(id)
        }
      })
    })
    return Array.from(ids)
  }

  const update = (state: StoreState): void => {
    const selected = selectedIds(state)
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

  // subscribe, not watch: this fires after every mutation whatever it touched,
  // so it does not depend on a deep getter being tracked correctly. The
  // selection is reached through several mutations (SET_PUBLICBODY,
  // SET_PUBLICBODIES, SET_PUBLICBODY_ID, ADD_PUBLICBODY_ID,
  // REMOVE_PUBLICBODY_ID) and more than one chooser component.
  //
  // Deliberately not run eagerly: the server already rendered the right state
  // for a body chosen before load, and the store has not hydrated at this
  // point, so an eager pass would hide a correct notice.
  store.subscribe((_mutation: unknown, state: StoreState) => {
    update(state)
  })

  // Diagnostic. The selection lives in the store and its DOM shape changes with
  // the step, so "why is the notice hidden?" is otherwise hard to answer from a
  // console. Reports what the notice believes:
  //
  //   fdsFaxNotice()
  //   -> { selected: ['26', '31'], diverted: ['26'], hidden: false }
  //
  // Remove once the multi-body flow is confirmed working in the wild.
  ;(window as unknown as Record<string, unknown>).fdsFaxNotice = () => {
    const state = store.state as StoreState
    const selected = selectedIds(state)
    return {
      selected,
      diverted: selected.filter((id) => faxIds.has(id)),
      knownFaxIds: Array.from(faxIds),
      hidden: notice.hidden
    }
  }
}
