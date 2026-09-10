// Version-aware FROST / OData annotation field names.
//
// STA 1.x uses ``@iot.*``; STA 2.0 aligns with OData 4.01
// (``id``, ``@id``, ``@navigationLink``, ``@nextLink``, ``@count``).
// The active version is taken from ``state.frostVersion``, or deduced from a
// FROST URL path suffix (``/v1.0/``, ``/v1.1/``, ``/v2.0/``).

function frostVersionFromUrl(url) {
    if (!url) return state.frostVersion;
    const match = String(url).match(/\/(v\d+(?:\.\d+)?)(?:\/|$|\?)/i);
    if (!match) return state.frostVersion;
    let version = match[1].toLowerCase();
    if (version === 'v1') version = 'v1.0';
    else if (version === 'v2') version = 'v2.0';
    return version;
}

function resolveFrostVersion(versionOrUrl) {
    if (versionOrUrl == null || versionOrUrl === '') {
        return state.frostVersion;
    }
    const value = String(versionOrUrl);
    if (/^https?:\/\//i.test(value) || value.includes('/v')) {
        return frostVersionFromUrl(value);
    }
    return value;
}

function isFrostV2(versionOrUrl) {
    const version = resolveFrostVersion(versionOrUrl);
    return String(version).replace(/^v/i, '').startsWith('2');
}

function frostFields(versionOrUrl) {
    if (isFrostV2(versionOrUrl)) {
        return {
            id: 'id',
            selfLink: '@id',
            nextLink: '@nextLink',
            count: '@count',
            navLinkSuffix: '@navigationLink',
        };
    }
    return {
        id: '@iot.id',
        selfLink: '@iot.selfLink',
        nextLink: '@iot.nextLink',
        count: '@iot.count',
        navLinkSuffix: '@iot.navigationLink',
    };
}

function frostIdField(versionOrUrl) {
    return frostFields(versionOrUrl).id;
}

function frostEntityId(entity, versionOrUrl) {
    if (!entity) return undefined;
    const { id } = frostFields(versionOrUrl);
    if (entity[id] != null) return entity[id];
    // Tolerate either annotation form during migration / mixed caches.
    return entity['@iot.id'] ?? entity['id'];
}

/** Total matching entities from a `$count=true` response, or null if absent. */
function frostCount(payload, versionOrUrl) {
    if (!payload) return null;
    const { count } = frostFields(versionOrUrl);
    const value = payload[count] ?? payload['@iot.count'] ?? payload['@count'];
    return Number.isFinite(value) ? value : null;
}

function frostNextLink(payload, versionOrUrl) {
    if (!payload) return null;
    const { nextLink } = frostFields(versionOrUrl);
    return payload[nextLink] || payload['@iot.nextLink'] || payload['@nextLink'] || null;
}

function frostSelfLink(entity, versionOrUrl) {
    if (!entity) return null;
    const { selfLink } = frostFields(versionOrUrl);
    return entity[selfLink] || entity['@iot.selfLink'] || entity['@id'] || null;
}

function frostNavLink(entity, relation, versionOrUrl) {
    if (!entity || !relation) return undefined;
    const { navLinkSuffix } = frostFields(versionOrUrl);
    return (
        entity[`${relation}${navLinkSuffix}`]
        ?? entity[`${relation}@iot.navigationLink`]
        ?? entity[`${relation}@navigationLink`]
    );
}

function frostIdRecord(id, versionOrUrl) {
    return { [frostIdField(versionOrUrl)]: id };
}

/** Unit symbol: STA 1.x ``unitOfMeasurement.symbol``; STA 2.0 ``resultType.uom``. */
function frostUnitSymbol(datastream) {
    if (!datastream) return '';
    return (
        datastream.unitOfMeasurement?.symbol
        || datastream.resultType?.uom?.symbol
        || datastream.resultType?.uom?.code
        || ''
    );
}
