import QtQuick
import QtQuick.Controls
ToolButton {
    id: control
    property string label: ""
    Accessible.name: label
    hoverEnabled: true
    opacity: 1
    contentItem: Item {}
    background: Rectangle {
        radius: 4
        color: !control.enabled ? "#8820252C" : control.down ? "#22FFFFFF" : control.hovered ? "#0CFFFFFF" : "transparent"
        border.color: control.activeFocus ? "#B19AFF" : "transparent"
        border.width: 1
    }
    ToolTip.visible: hovered
    ToolTip.delay: 700
    ToolTip.text: label
}
