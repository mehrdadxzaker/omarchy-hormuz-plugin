import QtQuick
import qs.Commons
import qs.Commons as Commons

Rectangle {
    id: root
    property string text: ""
    property string fontFamily: Style.font.family
    property bool selected: false
    signal clicked()

    implicitHeight: Style.space(36)
    radius: Style.space(6)
    color: selected || mouse.containsMouse ? Commons.Color.accent : Commons.Color.background
    border.color: selected ? Commons.Color.accent : Commons.Color.foreground
    border.width: 1
    opacity: enabled ? 1 : 0.4
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: if (enabled) clicked()

    Text {
        anchors.centerIn: parent
        width: parent.width - Style.space(12)
        text: root.text
        textFormat: Text.PlainText
        color: root.selected || mouse.containsMouse ? Commons.Color.background : Commons.Color.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
