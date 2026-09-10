import QtQuick
import QtQuick.Controls

ListView {
    id: list
    property var entries: []
    property bool busy: false
    signal removeRequested(string path)
    model: entries
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    delegate: Item {
        required property var modelData
        width: list.width
        height: 25
        Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: "#343941" }
        Image { x: 9; y: 6; width: 12; height: 14; source: modelData.kind === "raw" ? "assets/file.svg" : "assets/zip-file.svg" }
        Text { x: 27; width: 163; height: 25; text: modelData.name; color: "#F1EFF7"; font.pixelSize: 8; elide: Text.ElideMiddle; verticalAlignment: Text.AlignVCenter }
        Text { x: 206; width: 64; height: 25; text: modelData.sizeText; color: "#DBDCE5"; font.pixelSize: 8; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
        Text { x: 284; width: 115; height: 25; text: modelData.status; color: modelData.verified ? "#81D5A4" : "#DBDCE5"; font.pixelSize: 8; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
        ToolButton {
            objectName: "removeFileButton"
            x: 409; y: 1; width: 25; height: 24
            enabled: !list.busy
            background: null
            contentItem: Image { source: "assets/close.svg"; sourceSize: Qt.size(10, 10); fillMode: Image.PreserveAspectFit }
            Accessible.name: "Remove " + modelData.name + " from list"
            onClicked: list.removeRequested(modelData.path)
        }
    }
    Text { anchors.centerIn: parent; visible: list.count === 0; text: "Add files to get started"; font.pixelSize: 9; color: "#9EA3B2" }
}
