import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Commons as Commons
import qs.Ui as Ui
import "Model.js" as Model

Ui.Panel {
    id: root
    moduleName: "io.hormuz.optimizer"
    manageIpc: false
    property var anchorItem: null
    property var hostWidget: null
    required property var backend
    property int selectedAction: 0
    readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

    function switchPanel(direction) {
        return bar && typeof bar.switchPanelFrom === "function"
            ? bar.switchPanelFrom(hostWidget || root, direction) : false;
    }
    function activateAction() {
        if (selectedAction === 0) backend.launch();
        else if (selectedAction === 1) backend.toggleOptimization();
        else backend.refresh();
    }
    function revealActions() {
        var bottom = actions.y + actions.height;
        if (bottom > scroll.contentY + scroll.height)
            scroll.contentY = Math.min(Math.max(0, scroll.contentHeight - scroll.height),
                                      Math.max(0, bottom - scroll.height));
        else if (actions.y < scroll.contentY)
            scroll.contentY = Math.max(0, actions.y);
    }
    onOpenedChanged: if (opened) {
        backend.refresh();
        selectedAction = 0;
        Qt.callLater(function() { keys.forceActiveFocus(); });
    }

    Ui.KeyboardPanel {
        id: surface
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        popoutSwitching: root.popoutSwitching
        popoutSwitchClosing: root.popoutSwitchClosing
        focusTarget: keys
        contentWidth: fittedContentWidth(Style.space(380))
        contentHeight: fittedContentHeight(content.implicitHeight, Style.space(640))

        Ui.PanelKeyCatcher {
            id: keys
            anchors.fill: parent
            onCloseRequested: root.close()
            onTabRequested: function(direction) { root.switchPanel(direction); }
            onMoveRequested: function(dx, dy) {
                root.selectedAction = Math.max(0, Math.min(2, root.selectedAction + (dx || dy)));
                Qt.callLater(root.revealActions);
            }
            onActivateRequested: root.activateAction()
            onTextKey: function(text) { if (text.toLowerCase() === "r") root.backend.refresh(); }

            Flickable {
                id: scroll
                anchors.fill: parent
                contentWidth: width
                contentHeight: content.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.VerticalFlick
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                Column {
                    id: content
                    width: parent.width
                    spacing: Style.space(18)

                    Column {
                        width: parent.width
                        spacing: Style.space(5)
                        Text {
                            text: "HORMUZ"
                            color: Commons.Color.accent
                            font.family: root.fontFamily
                            font.pixelSize: Style.font.heading
                            font.bold: true
                            font.letterSpacing: Style.space(2)
                        }
                        Text {
                            width: parent.width
                            text: "Personal Optimizer · Linux preview"
                            color: Commons.Color.foreground
                            font.family: root.fontFamily
                            font.pixelSize: Style.font.body
                        }
                        Text {
                            width: parent.width
                            text: root.backend.profile
                            textFormat: Text.PlainText
                            color: Commons.Color.foreground
                            opacity: 0.65
                            font.family: root.fontFamily
                            font.pixelSize: Style.font.caption
                            elide: Text.ElideRight
                        }
                    }

                    Metric {
                        width: parent.width
                        label: "Estimated input tokens avoided"
                        value: Model.metric(root.backend.snapshot, "tokensSaved", root.backend.ready)
                        hint: root.backend.ready
                            ? Model.percent(root.backend.snapshot.tokenPercent) + " across captured traffic · local estimate"
                            : "A saved profile and a readable local report are required."
                        fontFamily: root.fontFamily
                        prominent: true
                    }

                    Row {
                        width: parent.width
                        spacing: Style.space(12)
                        Metric {
                            width: (parent.width - parent.spacing * 2) / 3
                            label: "Requests"
                            value: Model.metric(root.backend.snapshot, "requests", root.backend.ready)
                            fontFamily: root.fontFamily
                        }
                        Metric {
                            width: (parent.width - parent.spacing * 2) / 3
                            label: "Eligible"
                            value: Model.metric(root.backend.snapshot, "eligible", root.backend.ready)
                            fontFamily: root.fontFamily
                        }
                        Metric {
                            width: (parent.width - parent.spacing * 2) / 3
                            label: "Transformed"
                            value: Model.metric(root.backend.snapshot, "transformed", root.backend.ready)
                            fontFamily: root.fontFamily
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: Style.space(12)
                        Metric {
                            width: (parent.width - parent.spacing) / 2
                            label: "Request bytes avoided"
                            value: Model.metric(root.backend.snapshot, "bytesSaved", root.backend.ready)
                            hint: "Exact serialized bytes"
                            fontFamily: root.fontFamily
                        }
                        Metric {
                            width: (parent.width - parent.spacing) / 2
                            label: "Provider cache tokens"
                            value: Model.metric(root.backend.snapshot, "cacheReadTokens", root.backend.ready)
                            hint: "Provider reported · — if missing"
                            fontFamily: root.fontFamily
                        }
                    }

                    Text {
                        width: parent.width
                        text: root.backend.busy ? "Reading local report…" : root.backend.message
                        textFormat: Text.PlainText
                        color: root.backend.ready ? Commons.Color.foreground : Commons.Color.urgent
                        opacity: root.backend.ready ? 0.65 : 1
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.bodySmall
                        wrapMode: Text.WordWrap
                    }

                    Row {
                        width: parent.width
                        spacing: Style.space(8)
                        id: actions
                        ActionButton {
                            width: (parent.width - parent.spacing * 2) / 3
                            text: "Launch agent"
                            enabled: root.backend.ready && !root.backend.busy
                            selected: root.selectedAction === 0
                            fontFamily: root.fontFamily
                            onClicked: root.backend.launch()
                        }
                        ActionButton {
                            width: (parent.width - parent.spacing * 2) / 3
                            text: root.backend.ready && root.backend.snapshot.enabled ? "Turn off" : "Turn on"
                            enabled: root.backend.ready && !root.backend.busy
                            selected: root.selectedAction === 1
                            fontFamily: root.fontFamily
                            onClicked: root.backend.toggleOptimization()
                        }
                        ActionButton {
                            width: (parent.width - parent.spacing * 2) / 3
                            text: "Refresh"
                            enabled: !root.backend.busy
                            selected: root.selectedAction === 2
                            fontFamily: root.fontFamily
                            onClicked: root.backend.refresh()
                        }
                    }

                    Text {
                        width: parent.width
                        text: "Measurements stay local. Token estimates do not establish provider bill savings.\n\n← → select · Enter activate · R refresh · Esc close"
                        color: Commons.Color.foreground
                        opacity: 0.65
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.caption
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
