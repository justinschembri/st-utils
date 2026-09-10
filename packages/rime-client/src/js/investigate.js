// Entity investigation page.
//
// Same machine as the query builder — pick an entity type, fetch, render — but
// where query.html renders raw JSON, this renders structured rows you can expand
// in place and then walk through the STA graph by following
// `@iot.navigationLink` (via frostNavLink() in js/frost-fields.js).
//
// Read-only. Nothing here writes to the STA server.

const inv = {
    // Navigation trail. Each level is {label, url, entityType}. The last entry
    // is what is on screen; clicking an earlier one truncates back to it.
    trail: [],
    rows: [],
    nextLink: null,
    // Guards against a slow response for an abandoned view overwriting a newer
    // one — same idea as state.fetchGeneration on the map.
    generation: 0,
};

const el = {};

function cacheElements() {
    [
        'invEntity', 'invSearch', 'invMeta', 'invStatus', 'invList', 'invMore',
        'invBreadcrumb',
    ].forEach(id => { el[id] = document.getElementById(id); });
}

// ── endpoint ───────────────────────────────────────────────────────────────
// Owned by the shared connection control (js/connection.js).
function currentRoot() {
    return state.isConfigured ? state.frostRoot : '';
}

// ── presentation helpers ───────────────────────────────────────────────────

/**
 * Human label for an entity. Most STA types carry `name`; Observations do not,
 * so fall back to their result and time, then to the id.
 */
function entityLabel(entity, entityType) {
    if (entity?.name) return entity.name;
    if (entityType === 'Observations') {
        const result = entity?.result;
        const shown = Array.isArray(result) ? `[${result.length} values]` : result;
        return shown !== undefined && shown !== null ? String(shown) : 'Observation';
    }
    if (entityType === 'HistoricalLocations' && entity?.time) return String(entity.time);
    const id = frostEntityId(entity, state.frostVersion);
    return id != null ? `#${id}` : '(unnamed)';
}

/** Short secondary line for a row, without expanding it. */
function entitySubtitle(entity, entityType) {
    if (entity?.description) return entity.description;
    if (entityType === 'Observations' && entity?.phenomenonTime) {
        return String(entity.phenomenonTime);
    }
    if (entityType === 'Datastreams' && entity?.unitOfMeasurement?.symbol) {
        return entity.unitOfMeasurement.symbol;
    }
    return '';
}

/** Scalar/JSON properties worth showing, excluding annotations and nav links. */
function entityProperties(entity) {
    return Object.entries(entity || {})
        .filter(([key]) => !key.startsWith('@') && !key.includes('@iot.'))
        .map(([key, value]) => [key, value]);
}

/** Navigation relations actually present on this entity payload. */
function entityRelations(entity, entityType) {
    const declared = STA_NAV_PROPERTIES[entityType] || [];
    // Singular relations (Thing, Sensor) are not in the plural map, so also
    // pick up anything the payload itself advertises as a navigation link.
    const fromPayload = Object.keys(entity || {})
        .filter(k => k.includes('avigationLink'))
        .map(k => k.split('@')[0]);
    return [...new Set([...declared, ...fromPayload])]
        .filter(rel => frostNavLink(entity, rel, state.frostVersion));
}

/**
 * Deep links back to the map for entities the map can actually show.
 *
 * The endpoint travels in the URL as well as localStorage so a link stays
 * correct if it is copied into another tab or shared.
 */
function entityActions(entity, entityType) {
    const id = frostEntityId(entity, state.frostVersion);
    if (id == null) return [];

    const params = new URLSearchParams();
    if (state.frostBase) {
        params.set('sta', state.frostBase);
        params.set('version', state.frostVersion);
    }

    if (entityType === 'Datastreams') {
        params.set('datastream', id);
        return [
            { label: '📈 Chart this datastream', href: `index.html?${params}` },
            { label: '⤓ Download CSV', onClick: (btn) => downloadDatastreamCsv(entity, btn) },
        ];
    }
    if (entityType === 'Things') {
        params.set('thing', id);
        return [{ label: '📍 Show on map', href: `index.html?${params}` }];
    }
    return [];
}

/**
 * Export every observation of a datastream as CSV.
 *
 * Feedback goes on the button rather than the page status line: the row may be
 * scrolled far from the top, and a large datastream takes several pages to
 * fetch, so the progress needs to be where the user is looking.
 */
async function downloadDatastreamCsv(entity, button) {
    const id = frostEntityId(entity, state.frostVersion);
    const label = button.textContent;
    button.disabled = true;

    try {
        const { csv, count, truncated } = await datastreamObservationsCsv(id, {
            onProgress: n => { button.textContent = `⤓ ${n.toLocaleString()} rows…`; },
        });

        if (!count) {
            button.textContent = 'No observations';
            setTimeout(() => { button.textContent = label; button.disabled = false; }, 2000);
            return;
        }

        const name = sanitizeDownloadFilename(entity.name || `datastream_${id}`);
        triggerFileDownload(csv, `${name}.csv`);
        button.textContent = truncated
            ? `⤓ ${count.toLocaleString()} rows (capped)`
            : `⤓ ${count.toLocaleString()} rows`;
    } catch (err) {
        button.textContent = 'Download failed';
        setStatus(`Download failed: ${err.message}`, 'error');
    } finally {
        setTimeout(() => { button.textContent = label; button.disabled = false; }, 2500);
    }
}

function formatValue(value) {
    if (value === null) return 'null';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
}

// ── fetching ───────────────────────────────────────────────────────────────
function setStatus(message, kind) {
    if (!message) { el.invStatus.hidden = true; return; }
    el.invStatus.hidden = false;
    el.invStatus.textContent = message;
    el.invStatus.className = `inv-status inv-status-${kind || 'info'}`;
}

const INV_PAGE_SIZE = 50;

/** Load a level: either a collection URL or the current entity-type root. */
async function loadLevel(url, { append = false } = {}) {
    const generation = ++inv.generation;
    const target = url || collectionUrl();
    if (!target) {
        setStatus('Set a server URL first.', 'error');
        return;
    }

    setStatus('Loading…', 'info');
    try {
        const response = await frostFetch(target);
        const text = await response.text();
        if (generation !== inv.generation) return;   // a newer view won

        if (!response.ok) {
            // 401 with no credentials is a different problem from 401 with
            // them: say which, instead of blaming the password either way.
            if (response.status === 401) {
                setStatus(
                    state.frostReadAuth
                        ? 'Unauthorized — those credentials were rejected.'
                        : 'This server requires credentials. Use the Credentials button.',
                    'error',
                );
            } else {
                setStatus(`HTTP ${response.status} ${response.statusText}`, 'error');
            }
            if (!append) renderRows([]);
            return;
        }

        const payload = JSON.parse(text);
        // A collection responds with `value`; a single entity responds bare.
        const rows = Array.isArray(payload.value) ? payload.value : [payload];
        inv.rows = append ? [...inv.rows, ...rows] : rows;
        inv.nextLink = frostNextLink(payload, state.frostVersion);

        const total = frostCount(payload, state.frostVersion);
        el.invMeta.textContent = total != null && total > inv.rows.length
            ? `${inv.rows.length} of ${total}`
            : `${inv.rows.length} row${inv.rows.length === 1 ? '' : 's'}`;

        setStatus('', null);
        renderRows(inv.rows);
        el.invMore.hidden = !inv.nextLink;
    } catch (err) {
        if (generation !== inv.generation) return;
        const cors = err instanceof TypeError;
        setStatus(
            cors
                ? 'Request failed — server unreachable, or it did not send CORS headers.'
                : `Request failed: ${err.message}`,
            'error',
        );
        if (!append) renderRows([]);
    }
}

/** URL for the current entity type at the current root, with a name filter. */
function collectionUrl() {
    const root = currentRoot();
    if (!root) return '';
    const term = el.invSearch.value.trim();
    const entity = el.invEntity.value;
    // Only Things/Sensors/etc have `name`; filtering Observations by it is a
    // 400, so the search box only applies where the property exists.
    const supportsName = (STA_COMMON_FIELDS[entity] || []).includes('name');
    const filter = term && supportsName
        ? odataFilterClause(
            { field: 'name', operator: isFrostV2(state.frostVersion) ? 'contains' : 'substringof', value: term },
            state.frostVersion)
        : '';
    return buildODataUrl({
        root,
        entity,
        params: { $top: INV_PAGE_SIZE, $count: true, $filter: filter },
    });
}

// ── rendering ──────────────────────────────────────────────────────────────
function currentEntityType() {
    return inv.trail.length ? inv.trail[inv.trail.length - 1].entityType : el.invEntity.value;
}

function renderRows(rows) {
    const entityType = currentEntityType();
    el.invList.innerHTML = '';

    if (!rows.length) {
        const empty = document.createElement('li');
        empty.className = 'inv-empty';
        empty.textContent = 'Nothing here.';
        el.invList.appendChild(empty);
        return;
    }

    rows.forEach(entity => {
        const id = frostEntityId(entity, state.frostVersion);

        const row = document.createElement('li');
        row.className = 'inv-row';

        const head = document.createElement('button');
        head.className = 'inv-row-head';
        head.type = 'button';
        head.setAttribute('aria-expanded', 'false');
        head.innerHTML = `
            <span class="inv-caret" aria-hidden="true">▸</span>
            <span class="inv-row-text">
                <span class="inv-row-name"></span>
                <span class="inv-row-sub"></span>
            </span>
            <span class="inv-row-id"></span>`;
        head.querySelector('.inv-row-name').textContent = entityLabel(entity, entityType);
        head.querySelector('.inv-row-sub').textContent = entitySubtitle(entity, entityType);
        head.querySelector('.inv-row-id').textContent = id != null ? `#${id}` : '';

        const body = document.createElement('div');
        body.className = 'inv-row-body';
        body.hidden = true;

        head.addEventListener('click', () => {
            const open = body.hidden;
            body.hidden = !open;
            head.setAttribute('aria-expanded', String(open));
            row.classList.toggle('is-open', open);
            if (open && !body.dataset.built) {
                buildRowBody(body, entity, entityType);
                body.dataset.built = '1';
            }
        });

        row.append(head, body);
        el.invList.appendChild(row);
    });
}

function buildRowBody(body, entity, entityType) {
    const props = entityProperties(entity);
    if (props.length) {
        const table = document.createElement('dl');
        table.className = 'inv-props';
        props.forEach(([key, value]) => {
            const dt = document.createElement('dt');
            dt.textContent = key;
            const dd = document.createElement('dd');
            const formatted = formatValue(value);
            if (typeof value === 'object' && value !== null) {
                const pre = document.createElement('pre');
                pre.textContent = formatted;
                dd.appendChild(pre);
            } else {
                dd.textContent = formatted;
            }
            table.append(dt, dd);
        });
        body.appendChild(table);
    }

    const relations = entityRelations(entity, entityType);
    if (relations.length) {
        const nav = document.createElement('div');
        nav.className = 'inv-relations';
        const heading = document.createElement('span');
        heading.className = 'inv-relations-label';
        heading.textContent = 'Related';
        nav.appendChild(heading);

        relations.forEach(rel => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'qb-chip inv-rel-chip';
            chip.textContent = rel;
            chip.addEventListener('click', (e) => {
                e.stopPropagation();
                const link = frostNavLink(entity, rel, state.frostVersion);
                if (link) descend(rel, link, entity, entityLabel(entity, entityType), entityType);
            });
            nav.appendChild(chip);
        });
        body.appendChild(nav);
    }

    // Hand-off to the map. Without this the page dead-ends: you can find a
    // datastream and then have no way to look at its data.
    const actions = entityActions(entity, entityType);
    if (actions.length) {
        const bar = document.createElement('div');
        bar.className = 'inv-actions';
        actions.forEach(({ label, href, onClick }) => {
            const node = document.createElement(href ? 'a' : 'button');
            node.className = 'inv-action';
            node.textContent = label;
            if (href) {
                node.href = href;
            } else {
                node.type = 'button';
                node.addEventListener('click', (e) => { e.stopPropagation(); onClick(node); });
            }
            bar.appendChild(node);
        });
        body.appendChild(bar);
    }

    const self = frostSelfLink(entity, state.frostVersion);
    if (self) {
        const link = document.createElement('a');
        link.className = 'inv-selflink';
        link.href = self;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Open raw JSON ↗';
        body.appendChild(link);
    }
}

// ── navigation ─────────────────────────────────────────────────────────────

/**
 * Follow a navigation link.
 *
 * Pushes two levels: the entity you drilled *from* (reachable by its selfLink)
 * and the relation itself. That makes every crumb navigable and lets the trail
 * read as a real path — `Things › Milesight AM103L › Datastreams › Sensor`.
 *
 * Walking the STA graph loops easily: Thing → Datastreams → a Datastream →
 * Thing lands you back where you started. Pushing blindly grew a trail with the
 * same step repeated, so a revisited URL truncates the trail back to its first
 * appearance instead of extending it.
 */
function descend(relation, url, parentEntity, parentLabel, parentType) {
    const parentUrl = frostSelfLink(parentEntity, state.frostVersion);

    const levels = [];
    if (parentUrl) {
        levels.push({ label: parentLabel, url: parentUrl, entityType: parentType });
    }
    levels.push({
        label: relation,
        url,
        // Singular relations (Thing, Sensor) resolve to one entity; the plural
        // form is what STA_NAV_PROPERTIES and the label helpers expect.
        entityType: relation.endsWith('s') ? relation : `${relation}s`,
    });

    for (const level of levels) {
        const seen = inv.trail.findIndex(existing => existing.url === level.url);
        if (seen !== -1) {
            inv.trail = inv.trail.slice(0, seen + 1);   // collapse the cycle
        } else {
            inv.trail.push(level);
        }
    }

    renderBreadcrumb();
    el.invSearch.value = '';
    loadLevel(inv.trail[inv.trail.length - 1].url);
}

/** Return to a trail index; -1 is the root collection. */
function goToLevel(index) {
    inv.trail = index < 0 ? [] : inv.trail.slice(0, index + 1);
    renderBreadcrumb();
    el.invSearch.value = '';
    loadLevel(index < 0 ? null : inv.trail[index].url);
}

function renderBreadcrumb() {
    el.invBreadcrumb.innerHTML = '';

    const root = document.createElement('button');
    root.type = 'button';
    root.className = 'inv-crumb';
    root.textContent = el.invEntity.value;
    root.addEventListener('click', () => goToLevel(-1));
    el.invBreadcrumb.appendChild(root);

    inv.trail.forEach((level, index) => {
        const sep = document.createElement('span');
        sep.className = 'inv-crumb-sep';
        sep.textContent = '›';
        el.invBreadcrumb.appendChild(sep);

        const crumb = document.createElement('button');
        crumb.type = 'button';
        crumb.className = 'inv-crumb';
        crumb.textContent = level.label;
        if (index === inv.trail.length - 1) crumb.classList.add('is-current');
        crumb.addEventListener('click', () => goToLevel(index));
        el.invBreadcrumb.appendChild(crumb);
    });

    el.invBreadcrumb.classList.toggle('has-trail', inv.trail.length > 0);
}

// ── wiring ─────────────────────────────────────────────────────────────────
function initInvestigate() {
    cacheElements();

    STA_ENTITY_TYPES.forEach(entity => {
        const option = document.createElement('option');
        option.value = entity;
        option.textContent = entity;
        el.invEntity.appendChild(option);
    });

    // Server, version and credentials are the shared control (js/connection.js);
    // applying one reloads the root collection against the new connection.
    mountConnectionControl(document.getElementById('connectionControl'), () => goToLevel(-1));

    el.invEntity.addEventListener('change', () => goToLevel(-1));

    // Debounced so typing does not fire a request per keystroke.
    let searchTimer = null;
    el.invSearch.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => goToLevel(-1), 300);
    });

    el.invMore.addEventListener('click', () => {
        if (inv.nextLink) loadLevel(inv.nextLink, { append: true });
    });

    renderBreadcrumb();
    if (state.isConfigured) {
        loadLevel();
    } else {
        setStatus('Set a server URL to begin.', 'info');
    }
}

document.addEventListener('DOMContentLoaded', initInvestigate);
