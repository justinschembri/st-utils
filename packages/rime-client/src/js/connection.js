// Shared STA connection control — server URL, API version and read credentials.
//
// One implementation for every page. This was previously hand-rolled three
// times (map, query builder, investigate) which let them drift: the map hid
// credentials behind a disclosure and reported "Invalid credentials" when none
// had been sent, while the other two did something different again.
//
// The markup is built here rather than duplicated across three HTML files. It
// uses the .endpoint-* classes already defined in styles.css, which all three
// pages load, so the styling comes along for free.
//
// Persistence, and why it differs per field:
//   * endpoint + version -> localStorage. A deliberate, reusable choice.
//   * credentials        -> sessionStorage. They must survive navigating from
//     Investigate to the map (a "Chart this datastream" link is useless if the
//     map then 401s), but should not outlive the browser session. sessionStorage
//     is per-tab and never written to disk.
//
// Note this is no weaker than the previous in-memory-only approach in practice:
// the pages already load Leaflet and Chart.js from public CDNs, and any of those
// scripts could read an in-memory token or hook fetch just as easily.

const STA_CREDENTIALS_STORAGE_KEY = 'rime.staAuth';

/** Base64 "user:pass" held for this tab, or null. Safe if storage is blocked. */
function readStoredCredentials() {
    try {
        return sessionStorage.getItem(STA_CREDENTIALS_STORAGE_KEY) || null;
    } catch (_) {
        return null;
    }
}

function storeCredentials(auth) {
    try {
        if (auth) sessionStorage.setItem(STA_CREDENTIALS_STORAGE_KEY, auth);
        else sessionStorage.removeItem(STA_CREDENTIALS_STORAGE_KEY);
    } catch (_) { /* non-fatal — credentials just won't survive navigation */ }
}

const CONNECTION_MARKUP = `
  <button class="endpoint-display" id="endpointDisplay" title="Change STA server">
    <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14" aria-hidden="true">
      <path fill-rule="evenodd" d="M2 5a2 2 0 012-2h12a2 2 0 012 2v2a2 2 0 01-2 2H4a2 2 0 01-2-2V5zm14 1a1 1 0 11-2 0 1 1 0 012 0zM2 13a2 2 0 012-2h12a2 2 0 012 2v2a2 2 0 01-2 2H4a2 2 0 01-2-2v-2zm14 1a1 1 0 11-2 0 1 1 0 012 0z" clip-rule="evenodd"/>
    </svg>
    <span id="endpointLabel">Connect to a server</span>
  </button>
  <div class="endpoint-popover" id="endpointPopover" hidden>
    <label class="endpoint-popover-label" for="endpointInput">Server URL</label>
    <div class="endpoint-input-row">
      <input type="text" id="endpointInput" class="endpoint-input"
             placeholder="https://sta.example.org" autocomplete="off" spellcheck="false">
    </div>
    <div class="endpoint-quickpicks" id="endpointQuickpicks"></div>

    <label class="endpoint-popover-label">API version</label>
    <div class="endpoint-version-group" id="endpointVersionGroup">
      <button class="endpoint-version-btn" data-version="v1.0" type="button">v1.0</button>
      <button class="endpoint-version-btn active" data-version="v1.1" type="button">v1.1</button>
      <button class="endpoint-version-btn" data-version="v2.0" type="button">v2.0</button>
    </div>

    <label class="endpoint-popover-label">Credentials <span class="qb-hint">if the server needs them</span></label>
    <div class="endpoint-auth-fields" id="endpointAuthFields">
      <div class="endpoint-auth-row">
        <input type="text" id="endpointUsername" class="endpoint-input endpoint-input-half"
               placeholder="Username" autocomplete="username" spellcheck="false">
        <input type="password" id="endpointPassword" class="endpoint-input endpoint-input-half"
               placeholder="Password" autocomplete="current-password">
      </div>
    </div>

    <div class="endpoint-popover-footer">
      <p class="endpoint-hint" id="endpointHint">Kept for this browser tab only.</p>
      <button class="endpoint-apply-btn" id="endpointApply" title="Connect">
        <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14" aria-hidden="true">
          <path fill-rule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clip-rule="evenodd"/>
        </svg>
        Connect
      </button>
    </div>
  </div>`;

const ENDPOINT_HINT_DEFAULT = 'Kept for this browser tab only.';

// Assigned on mount so other modules can open the popover (app.js does this on
// an unconfigured boot).
let _openEndpointPopover = null;

function promptForEndpoint(message) {
    const hint = document.getElementById('endpointHint');
    if (hint) {
        hint.textContent = message || ENDPOINT_HINT_DEFAULT;
        hint.classList.toggle('endpoint-hint-warn', !!message);
    }
    if (_openEndpointPopover) _openEndpointPopover();
}

function clearEndpointHint() {
    const hint = document.getElementById('endpointHint');
    if (!hint) return;
    hint.textContent = ENDPOINT_HINT_DEFAULT;
    hint.classList.remove('endpoint-hint-warn');
}

/**
 * Build the control inside `container` and wire it up.
 *
 * @param {HTMLElement} container mount point; gets `.endpoint-switcher`.
 * @param {Function} onApply called after the user commits a new connection.
 */
function mountConnectionControl(container, onApply) {
    if (!container) return;
    container.classList.add('endpoint-switcher');
    container.innerHTML = CONNECTION_MARKUP;

    const display = container.querySelector('#endpointDisplay');
    const popover = container.querySelector('#endpointPopover');
    const input = container.querySelector('#endpointInput');
    const label = container.querySelector('#endpointLabel');
    const versionGroup = container.querySelector('#endpointVersionGroup');
    const usernameInput = container.querySelector('#endpointUsername');
    const passwordInput = container.querySelector('#endpointPassword');
    const quickpicks = container.querySelector('#endpointQuickpicks');
    const applyBtn = container.querySelector('#endpointApply');

    STA_KNOWN_SERVERS.forEach(server => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'endpoint-quickpick';
        btn.dataset.base = server.base;
        btn.textContent = server.label;
        btn.title = server.base;
        quickpicks.appendChild(btn);
    });

    function syncLabel() {
        if (!state.isConfigured) {
            label.textContent = 'Connect to a server';
            display.classList.add('unconfigured');
            display.classList.remove('has-auth');
            return;
        }
        label.textContent = `${state.frostBase.replace(/^https?:\/\//, '')} @ ${state.frostVersion}`;
        display.classList.remove('unconfigured');
        display.classList.toggle('has-auth', !!state.frostReadAuth);
    }

    function syncVersionButtons() {
        versionGroup.querySelectorAll('.endpoint-version-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.version === state.frostVersion);
        });
    }

    versionGroup.addEventListener('click', (e) => {
        const btn = e.target.closest('.endpoint-version-btn');
        if (!btn) return;
        state.frostVersion = btn.dataset.version;
        syncVersionButtons();
    });

    quickpicks.addEventListener('click', (e) => {
        const btn = e.target.closest('.endpoint-quickpick');
        if (!btn) return;
        input.value = btn.dataset.base;
        input.focus();
    });

    function openPopover() {
        input.value = state.frostBase;
        syncVersionButtons();
        if (state.frostReadAuth) {
            try {
                const decoded = atob(state.frostReadAuth);
                const colon = decoded.indexOf(':');
                usernameInput.value = decoded.substring(0, colon);
                passwordInput.value = decoded.substring(colon + 1);
            } catch (_) { /* ignore malformed auth */ }
        }
        popover.hidden = false;
        display.classList.add('active');
        input.focus();
        input.select();
    }

    function closePopover() {
        popover.hidden = true;
        display.classList.remove('active');
    }

    display.addEventListener('click', (e) => {
        e.stopPropagation();
        popover.hidden ? openPopover() : closePopover();
    });

    document.addEventListener('click', (e) => {
        if (!container.contains(e.target)) closePopover();
    });

    function applyConnection() {
        let raw = input.value.trim().replace(/\/+$/, '');

        // Tolerate a pasted URL that already carries its version segment.
        const versionMatch = raw.match(/\/(v\d+(?:\.\d+)?)$/i);
        if (versionMatch) {
            let version = versionMatch[1].toLowerCase();
            if (version === 'v1') version = 'v1.0';
            else if (version === 'v2') version = 'v2.0';
            if (['v1.0', 'v1.1', 'v2.0'].includes(version)) {
                state.frostVersion = version;
                syncVersionButtons();
            }
            raw = raw.replace(/\/(v\d+(?:\.\d+)?)$/i, '');
        }

        if (!raw) { closePopover(); return; }

        const user = usernameInput.value.trim();
        const pass = passwordInput.value;

        state.frostBase = raw;
        state.frostReadAuth = (user || pass) ? btoa(`${user}:${pass}`) : null;

        storeEndpoint(state.frostBase, state.frostVersion);
        storeCredentials(state.frostReadAuth);

        syncLabel();
        closePopover();
        if (typeof onApply === 'function') onApply();
    }

    applyBtn.addEventListener('click', applyConnection);
    [input, usernameInput, passwordInput].forEach(field => {
        field.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') applyConnection();
            if (e.key === 'Escape') closePopover();
        });
    });

    _openEndpointPopover = openPopover;
    syncLabel();
    syncVersionButtons();
}
