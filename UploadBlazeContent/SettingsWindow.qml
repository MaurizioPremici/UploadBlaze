import QtQuick
import QtQuick.Window

Window {
    id: settingsWindow
    objectName: "settingsWindow"
    property var controller: null
    property bool draftTested: false
    width: 569; height: 710
    minimumWidth: 569; minimumHeight: 710
    maximumWidth: 569; maximumHeight: 710
    visible: false
    color: "transparent"
    title: "UploadBlaze Settings"
    flags: Qt.Window | Qt.FramelessWindowHint
    modality: Qt.NonModal

    function loadDraft() {
        draftTested = false
        if (!controller) return
        var config = controller.settings
        panel.keyId = config.key_id || ""
        panel.applicationKey = ""
        panel.bucket = config.bucket || ""
        panel.prefix = config.prefix !== undefined ? config.prefix : "encrypted-backups/"
        panel.rememberKey = config.remember || false
    }
    onVisibleChanged: if (!visible) { panel.applicationKey = ""; panel.showPassword = false }
    SettingsPanel {
        id: panel
        objectName: "settingsForm"
        anchors.fill: parent
        busy: controller ? controller.busy : false
        connectionStatus: controller && settingsWindow.draftTested ? controller.testStatus : "Not tested"
    }
    Connections {
        target: panel
        function onKeyIdChanged() { settingsWindow.draftTested = false }
        function onApplicationKeyChanged() { settingsWindow.draftTested = false }
        function onBucketChanged() { settingsWindow.draftTested = false }
        function onPrefixChanged() { settingsWindow.draftTested = false }
    }
    Connections {
        target: controller
        function onSettingsSaved() { settingsWindow.hide() }
    }
    Item {
        width: 455; height: 568
        scale: 1.25; transformOrigin: Item.TopLeft
        MouseArea { x: 0; y: 0; width: 412; height: 60; onPressed: settingsWindow.startSystemMove() }
        ActionArea { x: 423; y: 7; width: 27; height: 27; label: "Close Settings"; onClicked: settingsWindow.hide() }
        ActionArea { x: 142; y: 522; width: 128; height: 31; label: "Cancel"; onClicked: settingsWindow.hide() }
        ActionArea {
            objectName: "saveSettingsButton"
            x: 280; y: 522; width: 148; height: 31; label: "Save Settings"
            enabled: controller !== null && !panel.busy
            onClicked: controller.saveSettings(panel.keyId, panel.applicationKey, panel.bucket, panel.prefix, panel.rememberKey)
        }
        ActionArea {
            objectName: "testConnectionButton"
            x: 28; y: 436; width: 400; height: 27; label: "Test Connection"
            enabled: controller !== null && !panel.busy
            onClicked: { settingsWindow.draftTested = true; controller.testConnection(panel.keyId, panel.applicationKey, panel.bucket, panel.prefix) }
        }
        ActionArea { x: 395; y: 185; width: 29; height: 25; label: "Show or hide application key"; onClicked: panel.showPassword = !panel.showPassword }
        ActionArea { x: 26; y: 385; width: 355; height: 36; label: "Remember key on this device"; enabled: !panel.busy; onClicked: panel.rememberKey = !panel.rememberKey }
    }
}
