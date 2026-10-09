import QtQuick
import qs.Ui as Ui

Ui.BarWidget {
    id: root
    moduleName: "io.hormuz.optimizer"

    readonly property bool opened: details.opened
    readonly property bool popoutSwitchClosing: details.popoutSwitchClosing

    function open() { details.open(); }
    function close() { details.close(); }
    function toggle() { details.toggle(); }
    function closeForPopoutSwitch() { details.closeForPopoutSwitch(); }

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    Service {
        id: optimizerService
        profile: String(root.setting("profile", "personal-codex"))
        cli: String(root.setting("hormuzCommand", "hormuz"))
        stateDirectory: String(root.setting("stateDirectory", ""))
    }

    Panel {
        id: details
        bar: root.bar
        anchorItem: button
        hostWidget: root
        backend: optimizerService
    }

    Ui.WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: root.vertical ? "H" :
              (root.setting("showLabel", true) ? "Hormuz" : "H") +
              (optimizerService.ready ? (optimizerService.snapshot.enabled ? " · on" : " · off") : " · ?")
        tooltipText: optimizerService.ready ?
                     "Hormuz · " + optimizerService.profile + " · local benefit report" :
                     "Hormuz · " + (optimizerService.busy ? "Reading local report…" : optimizerService.message)
        onPressed: function(buttonCode) {
            if (buttonCode === Qt.LeftButton) root.toggle();
            else if (buttonCode === Qt.MiddleButton) optimizerService.refresh();
        }
    }
}
