import QtQuick
import qs.Commons
import qs.Commons as Commons

Column {
    id: root
    property string label: ""
    property string value: "—"
    property string hint: ""
    property string fontFamily: Style.font.family
    property bool prominent: false
    spacing: Style.space(4)

    Text {
        width: parent.width
        text: root.label
        textFormat: Text.PlainText
        color: Commons.Color.foreground
        opacity: 0.65
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        wrapMode: Text.WordWrap
    }
    Text {
        width: parent.width
        text: root.value
        textFormat: Text.PlainText
        color: Commons.Color.foreground
        font.family: root.fontFamily
        font.pixelSize: root.prominent ? Style.font.displayLarge : Style.font.heading
        font.bold: true
        elide: Text.ElideRight
    }
    Text {
        visible: root.hint !== ""
        width: parent.width
        text: root.hint
        textFormat: Text.PlainText
        color: Commons.Color.foreground
        opacity: 0.65
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
    }
}
