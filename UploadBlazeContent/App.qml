import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Dialogs

Window {
    id: mainWindow
    objectName: "mainWindow"
    property var controller: typeof backend !== "undefined" ? backend : null
    width: 569; height: 710
    minimumWidth: 569; minimumHeight: 710
    maximumWidth: 569; maximumHeight: 710
    visible: true
    color: "transparent"
    title: "UploadBlaze"
    flags: Qt.Window | Qt.FramelessWindowHint

    onClosing: function(close) {
        if (controller && controller.busy) {
            close.accepted = false
            busyDialog.open()
        } else {
            settingsWindow.close()
        }
    }

    UploadBlaze {
        id: form
        objectName: "mainForm"
        anchors.fill: parent
        fileModel: mainWindow.controller ? mainWindow.controller.files : []
        busy: mainWindow.controller ? mainWindow.controller.busy : false
        bucketName: mainWindow.controller ? mainWindow.controller.bucketName : "No bucket selected"
        connectionText: mainWindow.controller ? mainWindow.controller.connectionText : "Not checked"
        statusText: mainWindow.controller ? mainWindow.controller.phase : "Ready"
        progressValue: mainWindow.controller ? mainWindow.controller.percent : 0
        activityText: mainWindow.controller ? mainWindow.controller.logText : ""
    }
    Connections {
        target: form.fileList
        function onRemoveRequested(path) { if (mainWindow.controller) mainWindow.controller.removeFile(path) }
    }
    Connections {
        target: mainWindow.controller
        function onErrorRaised(message) { errorDialog.text = message; errorDialog.open() }
    }
    Item {
        width: 455; height: 568
        scale: 1.25; transformOrigin: Item.TopLeft
        MouseArea {
            x: 0; y: 0; width: 310; height: 47
            onPressed: mainWindow.startSystemMove()
        }
        ActionArea {
            objectName: "settingsButton"
            x: 318; y: 10; width: 72; height: 30
            label: "Settings"
            onClicked: {
                settingsWindow.loadDraft()
                settingsWindow.x = Math.max(Screen.virtualX, Math.min(mainWindow.x + mainWindow.width + 12, Screen.virtualX + Screen.width - settingsWindow.width))
                settingsWindow.y = Math.max(Screen.virtualY, Math.min(mainWindow.y, Screen.virtualY + Screen.height - settingsWindow.height))
                settingsWindow.show()
                settingsWindow.raise()
                settingsWindow.requestActivate()
            }
        }
        ActionArea { x: 400; y: 8; width: 25; height: 28; label: "Minimize"; onClicked: mainWindow.showMinimized() }
        ActionArea { x: 426; y: 8; width: 27; height: 28; label: "Close"; onClicked: mainWindow.close() }
        ActionArea {
            objectName: "addFilesButton"
            x: 64; y: 102; width: 69; height: 22; label: "Add Files"
            enabled: !form.busy && mainWindow.controller !== null
            onClicked: fileDialog.open()
        }
        ActionArea {
            objectName: "zipButton"
            x: 10; y: 387; width: 100; height: 37; label: "Zip Files"
            enabled: !form.busy && mainWindow.controller !== null
            onClicked: mainWindow.controller.zipFiles()
        }
        ActionArea {
            objectName: "protectButton"
            x: 116; y: 387; width: 111; height: 37; label: "Protect Files"
            enabled: !form.busy && mainWindow.controller !== null
            onClicked: mainWindow.controller.protectFiles(form.password, form.confirmation)
        }
        ActionArea {
            objectName: "uploadButton"
            x: 233; y: 387; width: 133; height: 37; label: "Upload Backup"
            enabled: !form.busy && mainWindow.controller !== null
            onClicked: mainWindow.controller.uploadBackup()
        }
        ActionArea {
            objectName: "stopButton"
            x: 372; y: 387; width: 73; height: 37; label: "Stop"
            enabled: form.busy
            onClicked: mainWindow.controller.stop()
        }
        ActionArea { x: 198; y: 326; width: 20; height: 23; label: "Show or hide encryption passwords"; onClicked: form.showPassword = !form.showPassword }
        ActionArea { x: 411; y: 326; width: 22; height: 23; label: "Show or hide encryption passwords"; onClicked: form.showPassword = !form.showPassword }
        ActionArea {
            x: 400; y: 483; width: 43; height: 28; label: "Clear activity log"
            onClicked: if (mainWindow.controller) mainWindow.controller.clearLog()
        }
    }
    DropArea {
        anchors.fill: parent
        enabled: !form.busy
        onDropped: function(drop) {
            if (mainWindow.controller && drop.hasUrls) {
                mainWindow.controller.addPaths(drop.urls)
                drop.acceptProposedAction()
            }
        }
    }
    FileDialog {
        id: fileDialog
        title: "Add files or ZIP archives"
        fileMode: FileDialog.OpenFiles
        onAccepted: if (mainWindow.controller) mainWindow.controller.addPaths(selectedFiles)
    }
    MessageDialog {
        id: errorDialog
        title: "UploadBlaze"
        buttons: MessageDialog.Ok
    }
    MessageDialog {
        id: busyDialog
        title: "Operation in progress"
        text: "Use Stop and wait for the operation to finish before closing. Your originals will be kept unchanged."
        buttons: MessageDialog.Ok
    }
    SettingsWindow {
        id: settingsWindow
        controller: mainWindow.controller
    }
}
