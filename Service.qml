import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    property string profile: "personal-codex"
    property string cli: "hormuz"
    property string stateDirectory: ""
    property var snapshot: ({})
    property bool ready: false
    property bool busy: false
    property string message: "Open the panel to inspect a saved Hormuz profile."
    property bool initialized: false
    property bool refreshPending: false
    property bool received: false
    property bool timedOut: false
    property string requestStamp: ""

    function stamp() { return JSON.stringify([profile, cli, stateDirectory]); }
    function helperArguments(action) {
        var url = Qt.resolvedUrl("scripts/hormuz_plugin.py").toString();
        var path = decodeURIComponent(url.replace(/^file:\/\//, ""));
        return ["python3", path, action, "--cli", cli, "--profile", profile,
                "--state-directory", stateDirectory];
    }
    function invalidate() {
        ready = false;
        snapshot = {};
        if (!initialized) return;
        if (busy) refreshPending = true;
        else refresh();
    }
    function fail(text) {
        ready = false;
        snapshot = {};
        message = text;
    }
    function request(action) {
        if (busy || process.running) return;
        received = false;
        timedOut = false;
        refreshPending = false;
        requestStamp = stamp();
        busy = true;
        process.command = helperArguments(action);
        process.running = true;
    }
    function refresh() { request("status"); }
    function toggleOptimization() {
        if (ready && !busy) request(snapshot.enabled ? "off" : "on");
    }
    function receive(text) {
        received = true;
        if (timedOut || requestStamp !== stamp()) return;
        try {
            var value = JSON.parse(text);
            if (value.schema !== "hormuz.omarchy-status.v1" || value.profile !== profile)
                throw new Error("Invalid helper report");
            if (value.ok !== true) {
                fail(String(value.message || "Cannot read the local Hormuz report."));
                return;
            }
            snapshot = value;
            ready = true;
            message = "Local report · " + Qt.formatTime(new Date(), "HH:mm");
        } catch (error) {
            fail("Cannot read the helper report. Check the installed plugin files.");
        }
    }
    function launch() {
        if (!ready || busy) return;
        Quickshell.execDetached(["omarchy-launch-terminal"].concat(helperArguments("launch")));
        message = "Launch requested in a terminal. Refresh after the session to see new measurements.";
    }

    onProfileChanged: invalidate()
    onCliChanged: invalidate()
    onStateDirectoryChanged: invalidate()
    Component.onCompleted: { initialized = true; refresh(); }
    Component.onDestruction: process.running = false

    Process {
        id: process
        stdout: StdioCollector {
            onStreamFinished: root.receive(text)
        }
        // The helper never forwards raw CLI diagnostics into the shell.
        stderr: StdioCollector {}
        onExited: function(exitCode, exitStatus) {
            if (!root.received && !root.timedOut)
                root.fail("The helper could not start. Check Python 3 and the plugin files.");
            root.busy = false;
            if (root.refreshPending) Qt.callLater(root.refresh);
        }
    }
    // One bounded local operation at a time; no recurring timer or network polling.
    Timer {
        interval: 25000
        running: root.busy
        onTriggered: {
            root.timedOut = true;
            process.running = false;
            root.fail("Hormuz did not respond in time. Refresh to try again.");
            if (!process.running) root.busy = false;
        }
    }
}
