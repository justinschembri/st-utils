// Shared CSV export.
//
// The client is not where analysis happens — a researcher pulls the data into
// pandas or R. So getting a clean CSV out from wherever you found the data
// matters more than anything the pages can render.
//
// The map already had a good exporter (paged, date-ranged, ZIP-per-datastream)
// but it lived inside app.js and was reachable only from the Thing sidebar,
// scoped to a whole Thing. These helpers are the reusable core, so the
// investigate page can export a single datastream and the query builder can
// export whatever a query returned.

/** Filesystem-safe name; never empty. */
function sanitizeDownloadFilename(name) {
    return String(name).replace(/[^a-z0-9._-]+/gi, '_').replace(/_+/g, '_')
        .replace(/^_|_$/g, '') || 'data';
}

/** Quote a CSV field only when it needs it, doubling embedded quotes. */
function csvField(value) {
    if (value === null || value === undefined) return '';
    const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
    return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** Hand the browser a file. Revokes the object URL so nothing leaks. */
function triggerFileDownload(content, filename, mimeType = 'text/csv;charset=utf-8;') {
    const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// A query can match far more than a browser should hold in memory as one
// string. Stop at this many rows and tell the caller it was truncated, rather
// than freezing the tab.
const EXPORT_MAX_ROWS = 100000;

/**
 * Follow `nextLink` until the collection is exhausted or the cap is reached.
 *
 * @returns {Promise<{rows: Array, truncated: boolean}>}
 */
async function fetchAllRows(url, { onProgress = null, cap = EXPORT_MAX_ROWS } = {}) {
    const rows = [];
    let nextUrl = url;

    while (nextUrl && rows.length < cap) {
        const response = await frostFetch(nextUrl);
        if (!response.ok) throw new Error(`HTTP ${response.status} ${response.statusText}`);
        const payload = await response.json();

        const page = Array.isArray(payload.value) ? payload.value : [payload];
        rows.push(...page);
        if (onProgress) onProgress(rows.length);

        nextUrl = frostNextLink(payload, state.frostVersion);
        // A server may advertise next-links against its own public root, which
        // can differ from the scheme the browser is using.
        if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
    }

    return { rows: rows.slice(0, cap), truncated: rows.length >= cap && !!nextUrl };
}

/**
 * Flatten arbitrary STA entities to CSV.
 *
 * Columns are the union of every row's own keys, so a sparse collection does
 * not silently lose a field that only some rows carry. Navigation links and
 * annotations are dropped — they are addresses, not data — except the id,
 * which is what you need to join this export back to anything else.
 */
function rowsToCsv(rows) {
    if (!rows.length) return '';

    const idField = frostIdField(state.frostVersion);
    const columns = [];
    const seen = new Set();
    for (const row of rows) {
        for (const key of Object.keys(row)) {
            if (key !== idField && (key.startsWith('@') || key.includes('@iot.'))) continue;
            if (!seen.has(key)) { seen.add(key); columns.push(key); }
        }
    }

    const lines = [columns.map(csvField).join(',')];
    for (const row of rows) {
        lines.push(columns.map(column => csvField(row[column])).join(','));
    }
    return lines.join('\n');
}

/**
 * Every observation of one datastream, as CSV.
 *
 * Ordered oldest-first by phenomenonTime — the order you want in a dataframe,
 * and the opposite of the chart's newest-first fetch.
 */
async function datastreamObservationsCsv(datastreamId, { onProgress = null } = {}) {
    const params = new URLSearchParams();
    params.set('$select', 'phenomenonTime,resultTime,result');
    params.set('$orderby', `phenomenonTime asc,${frostIdField(state.frostVersion)} asc`);
    params.set('$top', '10000');

    const url = `${state.frostRoot}/Datastreams(${datastreamId})/Observations`
        + `?${params.toString().replace(/%24/g, '$')}`;

    const { rows, truncated } = await fetchAllRows(url, { onProgress });
    const header = 'phenomenonTime,resultTime,result';
    const lines = rows.map(o => [
        csvField(o.phenomenonTime),
        csvField(o.resultTime),
        csvField(o.result),
    ].join(','));

    return { csv: [header, ...lines].join('\n'), count: rows.length, truncated };
}
