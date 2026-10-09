function count(value) {
    return typeof value === "number" && isFinite(value)
        ? Math.round(value).toLocaleString(Qt.locale(), "f", 0) : "—";
}

function percent(value) {
    return typeof value === "number" && isFinite(value)
        ? value.toLocaleString(Qt.locale(), "f", 1) + "%" : "unavailable";
}

function metric(snapshot, key, ready) {
    return ready ? count(snapshot[key]) : "—";
}
