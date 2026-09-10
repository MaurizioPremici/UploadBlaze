import QtQuick
import QtQuick.Controls
ScrollView {
    id: view
    property string logText: ""
    clip: true
    TextArea {
        readOnly: true
        selectByMouse: true
        text: view.logText || "Waiting for files to be prepared."
        color: "#B9BECE"
        font.pixelSize: 7
        wrapMode: TextEdit.Wrap
        background: null
        padding: 0
        onTextChanged: cursorPosition = length
    }
}
