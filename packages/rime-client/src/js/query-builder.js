// OData query builder page.
//
// Read-only by design: it composes GET requests and shows the raw response.
// Nothing here writes to the STA server. The endpoint is shared with the map
// page via the same localStorage keys (see state.js), so switching servers on
// one page carries over to the other.

const qb = {
    filterRows: [],
    join: 'and',
    nextLink: null,
};

let _rowSeq = 0;

// ── element handles ────────────────────────────────────────────────────────
const el = {};

function cacheElements() {
    [
        'qbEndpoint', 'qbServerPreset', 'qbVersion', 'qbEntity', 'qbFilterRows',
        'qbAddFilter', 'qbJoin', 'qbFilterHint', 'qbSelect', 'qbExpand',
        'qbExpandChips', 'qbOrderBy', 'qbTop', 'qbSkip', 'qbCount', 'qbUrl',
        'qbCopy', 'qbRun', 'qbStatus', 'qbOutput', 'qbMeta', 'qbNext',
    ].forEach(id => { el[id] = document.getElementById(id); });
}

// ── endpoint ───────────────────────────────────────────────────────────────
function currentRoot() {
    const base = el.qbEndpoint.value.trim().replace(/\/+$/, '');
    if (!base) return '';
    return `${base}/${el.qbVersion.value}`;
}

function persistEndpoint() {
    const base = el.qbEndpoint.value.trim().replace(/\/+$/, '');
    // storeEndpoint() lives in state.js and owns the localStorage keys, so the
    // map page picks up whatever is chosen here.
    storeEndpoint(base, el.qbVersion.value);
}

// ── filter rows ────────────────────────────────────────────────────────────
function addFilterRow(initial = {}) {
    const row = {
        id: `row-${++_rowSeq}`,
        field: initial.field || '',
        operator: initial.operator || 'eq',
        value: initial.value || '',
    };
    qb.filterRows.push(row);
    renderFilterRows();
}

function removeFilterRow(id) {
    qb.filterRows = qb.filterRows.filter(r => r.id !== id);
    renderFilterRows();
    updateUrl();
}

function renderFilterRows() {
    const operators = odataFilterOperators(el.qbVersion.value);
    const fields = STA_COMMON_FIELDS[el.qbEntity.value] || [];

    el.qbFilterRows.innerHTML = '';
    qb.filterRows.forEach(row => {
        const wrap = document.createElement('div');
        wrap.className = 'qb-filter-row';

        const field = document.createElement('input');
        field.type = 'text';
        field.className = 'qb-input qb-input-field';
        field.placeholder = 'property';
        field.value = row.field;
        field.setAttribute('list', 'qbFieldOptions');
        field.addEventListener('input', () => { row.field = field.value; updateUrl(); });

        const op = document.createElement('select');
        op.className = 'qb-select';
        operators.forEach(o => {
            const option = document.createElement('option');
            option.value = o.value;
            option.textContent = o.label;
            if (o.value === row.operator) option.selected = true;
            op.appendChild(option);
        });
        op.addEventListener('change', () => { row.operator = op.value; updateUrl(); });

        const value = document.createElement('input');
        value.type = 'text';
        value.className = 'qb-input qb-input-value';
        value.placeholder = 'value';
        value.value = row.value;
        value.addEventListener('input', () => { row.value = value.value; updateUrl(); });

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'qb-remove';
        remove.textContent = '×';
        remove.title = 'Remove condition';
        remove.addEventListener('click', () => removeFilterRow(row.id));

        wrap.append(field, op, value, remove);
        el.qbFilterRows.appendChild(wrap);
    });

    // Datalist of suggested properties for the selected entity.
    let datalist = document.getElementById('qbFieldOptions');
    if (!datalist) {
        datalist = document.createElement('datalist');
        datalist.id = 'qbFieldOptions';
        document.body.appendChild(datalist);
    }
    datalist.innerHTML = '';
    fields.forEach(f => {
        const option = document.createElement('option');
        option.value = f;
        datalist.appendChild(option);
    });
}

// ── expand suggestions ─────────────────────────────────────────────────────
function renderExpandChips() {
    const nav = STA_NAV_PROPERTIES[el.qbEntity.value] || [];
    el.qbExpandChips.innerHTML = '';
    nav.forEach(rel => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'qb-chip';
        chip.textContent = rel;
        chip.addEventListener('click', () => {
            const current = el.qbExpand.value.split(',').map(s => s.trim()).filter(Boolean);
            if (!current.includes(rel)) current.push(rel);
            el.qbExpand.value = current.join(',');
            updateUrl();
        });
        el.qbExpandChips.appendChild(chip);
    });
}

// ── URL ────────────────────────────────────────────────────────────────────
function buildUrl() {
    const root = currentRoot();
    if (!root) return '';
    return buildODataUrl({
        root,
        entity: el.qbEntity.value,
        params: {
            $filter: odataCombineFilters(qb.filterRows, qb.join, el.qbVersion.value),
            $select: el.qbSelect.value,
            $expand: el.qbExpand.value,
            $orderby: el.qbOrderBy.value,
            $top: el.qbTop.value,
            $skip: el.qbSkip.value,
            $count: el.qbCount.checked,
        },
    });
}

function updateUrl() {
    const url = buildUrl();
    el.qbUrl.textContent = url || 'Set a server URL to build a query.';
    el.qbUrl.classList.toggle('qb-url-empty', !url);
    qb.nextLink = null;
    el.qbNext.hidden = true;
}

// ── run ────────────────────────────────────────────────────────────────────
function setStatus(message, kind) {
    if (!message) {
        el.qbStatus.hidden = true;
        return;
    }
    el.qbStatus.hidden = false;
    el.qbStatus.textContent = message;
    el.qbStatus.className = `qb-status qb-status-${kind || 'info'}`;
}

async function runQuery(url) {
    const target = url || buildUrl();
    if (!target) {
        setStatus('Set a server URL first.', 'error');
        return;
    }

    el.qbRun.disabled = true;
    setStatus('Running…', 'info');
    const started = performance.now();

    try {
        const response = await frostFetch(target);
        const elapsed = Math.round(performance.now() - started);
        const text = await response.text();

        let parsed = null;
        try { parsed = JSON.parse(text); } catch (_) { /* not JSON */ }

        el.qbOutput.textContent = parsed ? JSON.stringify(parsed, null, 2) : text;

        if (!response.ok) {
            setStatus(`HTTP ${response.status} ${response.statusText}`, 'error');
        } else {
            setStatus('', null);
        }

        // Result count and paging, both version-aware.
        const version = el.qbVersion.value;
        const rows = Array.isArray(parsed?.value) ? parsed.value.length : (parsed ? 1 : 0);
        const total = parsed ? (parsed[frostFields(version).count] ?? parsed['@iot.count'] ?? parsed['@count']) : undefined;
        el.qbMeta.textContent = [
            `${rows} row${rows === 1 ? '' : 's'}`,
            total != null ? `of ${total}` : '',
            `${elapsed} ms`,
            `HTTP ${response.status}`,
        ].filter(Boolean).join(' · ');

        qb.nextLink = parsed ? frostNextLink(parsed, version) : null;
        el.qbNext.hidden = !qb.nextLink;

    } catch (err) {
        // A cross-origin failure surfaces as an opaque TypeError; say so, since
        // "Failed to fetch" on its own sends people looking in the wrong place.
        const cors = err instanceof TypeError;
        setStatus(
            cors
                ? 'Request failed — server unreachable, or it did not send CORS headers.'
                : `Request failed: ${err.message}`,
            'error',
        );
        el.qbOutput.textContent = String(err);
        el.qbMeta.textContent = '';
        el.qbNext.hidden = true;
    } finally {
        el.qbRun.disabled = false;
    }
}

// ── wiring ─────────────────────────────────────────────────────────────────
function initQueryBuilder() {
    cacheElements();

    STA_ENTITY_TYPES.forEach(entity => {
        const option = document.createElement('option');
        option.value = entity;
        option.textContent = entity;
        el.qbEntity.appendChild(option);
    });

    // Known-server dropdown, from the same list the map's quick-picks use.
    const custom = document.createElement('option');
    custom.value = '';
    custom.textContent = 'Custom…';
    el.qbServerPreset.appendChild(custom);
    STA_KNOWN_SERVERS.forEach(server => {
        const option = document.createElement('option');
        option.value = server.base;
        option.textContent = server.label;
        option.title = server.base;
        el.qbServerPreset.appendChild(option);
    });

    el.qbEndpoint.value = state.frostBase || '';
    el.qbVersion.value = state.frostVersion || 'v1.1';

    /** Show the preset whose URL matches what is typed, else "Custom…". */
    function syncPreset() {
        const current = el.qbEndpoint.value.trim().replace(/\/+$/, '');
        const match = STA_KNOWN_SERVERS.find(s => s.base === current);
        el.qbServerPreset.value = match ? match.base : '';
    }
    syncPreset();

    el.qbServerPreset.addEventListener('change', () => {
        if (!el.qbServerPreset.value) return;   // "Custom…" — leave the field alone
        el.qbEndpoint.value = el.qbServerPreset.value;
        persistEndpoint();
        updateUrl();
    });

    const rerenderForVersion = () => {
        // v1.1 has substringof, v2.0 replaces it with contains — reset any row
        // whose operator does not exist in the newly selected version.
        const valid = new Set(odataFilterOperators(el.qbVersion.value).map(o => o.value));
        qb.filterRows.forEach(row => {
            if (!valid.has(row.operator)) row.operator = 'eq';
        });
        el.qbFilterHint.textContent = isFrostV2(el.qbVersion.value)
            ? 'v2.0 — OData 4.01 operators'
            : 'v1.1 — substringof, not contains';
        renderFilterRows();
        updateUrl();
    };

    el.qbEndpoint.addEventListener('input', () => { syncPreset(); updateUrl(); });
    el.qbEndpoint.addEventListener('change', persistEndpoint);
    el.qbVersion.addEventListener('change', () => { persistEndpoint(); rerenderForVersion(); });

    el.qbEntity.addEventListener('change', () => {
        renderFilterRows();
        renderExpandChips();
        updateUrl();
    });

    ['qbSelect', 'qbExpand', 'qbOrderBy', 'qbTop', 'qbSkip'].forEach(id => {
        el[id].addEventListener('input', updateUrl);
    });
    el.qbCount.addEventListener('change', updateUrl);

    el.qbAddFilter.addEventListener('click', () => { addFilterRow(); updateUrl(); });

    el.qbJoin.addEventListener('click', (e) => {
        const btn = e.target.closest('.qb-join-btn');
        if (!btn) return;
        qb.join = btn.dataset.join;
        el.qbJoin.querySelectorAll('.qb-join-btn').forEach(b => {
            b.classList.toggle('active', b === btn);
        });
        updateUrl();
    });

    el.qbRun.addEventListener('click', () => runQuery());
    el.qbNext.addEventListener('click', () => runQuery(qb.nextLink));

    el.qbCopy.addEventListener('click', async () => {
        const url = buildUrl();
        if (!url) return;
        try {
            await navigator.clipboard.writeText(url);
            el.qbCopy.textContent = 'Copied';
            setTimeout(() => { el.qbCopy.textContent = 'Copy'; }, 1200);
        } catch (_) {
            setStatus('Clipboard unavailable — select the URL and copy manually.', 'info');
        }
    });

    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') runQuery();
    });

    renderExpandChips();
    rerenderForVersion();
}

document.addEventListener('DOMContentLoaded', initQueryBuilder);
