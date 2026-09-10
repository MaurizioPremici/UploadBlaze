import QtQuick
import QtQuick.Controls

Item {
    id: form
    property bool busy: false
    property bool showPassword: false
    property bool rememberKey: false
    property string connectionStatus: "Not tested"
    property alias keyId: keyIdInput.text
    property alias applicationKey: keyInput.text
    property alias bucket: bucketInput.text
    property alias prefix: prefixInput.text
    width: 569
    height: 710

    Rectangle {
        id: root

        // Preserve the design coordinates while enlarging every visual by 25%.
        scale: 1.25
        transformOrigin: Item.TopLeft

        width: 455
        height: 568

        radius: 9

        color: "#1A1F25"

        border.width: 1
        border.color: "#49515E"

        clip: true
        antialiasing: true

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1

            radius: 8

            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: "#20252D"
                }

                GradientStop {
                    position: 1
                    color: "#181D23"
                }
            }
        }

        // =========================================================
        // HEADER
        // =========================================================

        Image {
            x: 18
            y: 15

            width: 30
            height: 30

            source: "assets/settings.svg"

            fillMode: Image.PreserveAspectFit
        }

        Text {
            x: 57
            y: 7

            width: 160
            height: 26

            text: "Settings"

            color: "#F4EFFC"

            font.family: Qt.application.font.family
            font.pixelSize: 16
            font.weight: Font.DemiBold

            verticalAlignment: Text.AlignVCenter
        }

        Text {
            x: 57
            y: 28

            width: 150
            height: 20

            text: "Backblaze B2"

            color: "#B2B6CA"

            font.family: Qt.application.font.family
            font.pixelSize: 10

            verticalAlignment: Text.AlignVCenter
        }

        Image {
            x: 424
            y: 10

            width: 17
            height: 17

            source: "assets/close.svg"
        }

        Rectangle {
            x: 0
            y: 60

            width: 455
            height: 1

            color: "#424953"
        }

        // =========================================================
        // APPLICATION KEY ID
        // =========================================================

        Text {
            x: 28
            y: 78

            width: 220
            height: 18

            text: "Application Key ID"

            color: "#F4EFFA"

            font.family: Qt.application.font.family
            font.pixelSize: 10
            font.weight: Font.DemiBold
        }

        Text {
            x: 28
            y: 92

            width: 220
            height: 17

            text: "keyID"

            color: "#ADB2C3"

            font.family: Qt.application.font.family
            font.pixelSize: 8
        }

        Rectangle {
            x: 28
            y: 108

            width: 400
            height: 27

            radius: 5

            color: "#20252C"

            border.width: 1
            border.color: "#737D97"

            TextField {
                    id: keyIdInput
                    objectName: "keyIdInput"
                    readOnly: form.busy
                    selectByMouse: true
                    background: null
                    padding: 0
                    placeholderTextColor: "#9EA3B2"
                    color: "#ECEAF4"
                x: 9
                y: 0

                width: 350
                height: 27

                text: ""
                    placeholderText: "Enter your key ID"

                font.family: Qt.application.font.family
                font.pixelSize: 8

                verticalAlignment: Text.AlignVCenter
            }
        }

        // =========================================================
        // APPLICATION KEY
        // =========================================================

        Text {
            x: 28
            y: 153

            width: 220
            height: 18

            text: "Application Key"

            color: "#F4EFFA"

            font.family: Qt.application.font.family
            font.pixelSize: 10
            font.weight: Font.DemiBold
        }

        Text {
            x: 28
            y: 168

            width: 220
            height: 17

            text: "applicationKey"

            color: "#ADB2C3"

            font.family: Qt.application.font.family
            font.pixelSize: 8
        }

        Rectangle {
            x: 28
            y: 184

            width: 400
            height: 27

            radius: 5

            color: "#20252C"

            border.width: 1
            border.color: "#737D97"

            TextField {
                    id: keyInput
                    objectName: "keyInput"
                    readOnly: form.busy
                    selectByMouse: true
                    echoMode: form.showPassword ? TextInput.Normal : TextInput.Password
                    inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                    background: null
                    padding: 0
                    placeholderTextColor: "#9EA3B2"
                    color: "#ECEAF4"
                x: 9
                y: 0

                width: 345
                height: 27

                text: ""
                    placeholderText: "Enter your application key"

                font.family: Qt.application.font.family
                font.pixelSize: 8

                verticalAlignment: Text.AlignVCenter
            }

            Image {
                x: 373
                y: 8

                width: 14
                height: 11

                source: "assets/eye.svg"
            }
        }

        // =========================================================
        // BUCKET NAME
        // =========================================================

        Text {
            x: 28
            y: 229

            width: 220
            height: 18

            text: "Bucket Name"

            color: "#F4EFFA"

            font.family: Qt.application.font.family
            font.pixelSize: 10
            font.weight: Font.DemiBold
        }

        Rectangle {
            x: 28
            y: 248

            width: 400
            height: 27

            radius: 5

            color: "#20252C"

            border.width: 1
            border.color: "#737D97"

            TextField {
                    id: bucketInput
                    objectName: "bucketInput"
                    readOnly: form.busy
                    selectByMouse: true
                    background: null
                    padding: 0
                    placeholderTextColor: "#9EA3B2"
                    color: "#ECEAF4"
                x: 9
                y: 0

                width: 330
                height: 27

                text: ""
                    placeholderText: "Enter your private bucket name"

                font.family: Qt.application.font.family
                font.pixelSize: 8

                verticalAlignment: Text.AlignVCenter
            }

        }

        // =========================================================
        // REMOTE FOLDER
        // =========================================================

        Text {
            x: 28
            y: 293

            width: 220
            height: 18

            text: "Remote Folder"

            color: "#F4EFFA"

            font.family: Qt.application.font.family
            font.pixelSize: 10
            font.weight: Font.DemiBold
        }

        Text {
            x: 28
            y: 307

            width: 220
            height: 17

            text: "Optional prefix"

            color: "#ADB2C3"

            font.family: Qt.application.font.family
            font.pixelSize: 8
        }

        Rectangle {
            x: 28
            y: 323

            width: 400
            height: 27

            radius: 5

            color: "#20252C"

            border.width: 1
            border.color: "#737D97"

            TextField {
                    id: prefixInput
                    objectName: "prefixInput"
                    readOnly: form.busy
                    selectByMouse: true
                    background: null
                    padding: 0
                    placeholderTextColor: "#9EA3B2"
                    color: "#ECEAF4"
                x: 9
                y: 0

                width: 350
                height: 27

                text: "encrypted-backups/"
                    placeholderText: "encrypted-backups/"

                font.family: Qt.application.font.family
                font.pixelSize: 8

                verticalAlignment: Text.AlignVCenter
            }
        }

        // =========================================================
        // SECURITY HINT
        // =========================================================

        Text {
            x: 28
            y: 363

            width: 390
            height: 18

            text: "Use an application key restricted to your backup bucket."

            color: "#B0B3C5"

            font.family: Qt.application.font.family
            font.pixelSize: 7
        }

        // =========================================================
        // REMEMBER KEY
        // =========================================================

        Rectangle {
            x: 28
            y: 390

            width: 14
            height: 14

            radius: 2

            color: "#20252B"

            border.width: 1
            border.color: "#8B96B0"
            Text { anchors.centerIn: parent; text: "✓"; visible: form.rememberKey; color: "#C69AFF"; font.pixelSize: 12 }

        }

        Text {
            x: 50
            y: 387

            width: 220
            height: 21

            text: "Remember key on this device"

            color: "#F0EDF6"

            font.family: Qt.application.font.family
            font.pixelSize: 8

            verticalAlignment: Text.AlignVCenter
        }

        Text {
            x: 50
            y: 405

            width: 260
            height: 17

            text: "Stored in the system credential store."

            color: "#AEB2C3"

            font.family: Qt.application.font.family
            font.pixelSize: 7
        }

        // =========================================================
        // TEST CONNECTION
        // =========================================================

        Rectangle {
            x: 28
            y: 436

            width: 400
            height: 27

            radius: 4

            color: "#20242C"

            border.width: 1
            border.color: "#7E84DE"

            Text {
                anchors.fill: parent

                text: "Test Connection"

                color: "#F0ECF8"

                font.family: Qt.application.font.family
                font.pixelSize: 8
                font.weight: Font.DemiBold

                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        Rectangle {
            x: 201
            y: 475

            width: 8
            height: 8

            radius: 4

            color: "#858D9F"
        }

        Text {
            x: 216
            y: 468

            width: 190
            height: 23

            text: form.connectionStatus
            elide: Text.ElideRight

            color: "#AFB3C3"

            font.family: Qt.application.font.family
            font.pixelSize: 8

            verticalAlignment: Text.AlignVCenter
        }

        // =========================================================
        // FOOTER
        // =========================================================

        Rectangle {
            x: 0
            y: 506

            width: 455
            height: 1

            color: "#424953"
        }

        Rectangle {
            id: cancelButton

            x: 142
            y: 522

            width: 128
            height: 31

            radius: 5

            color: "#22262F"

            border.width: 1
            border.color: "#7883C1"

            Text {
                anchors.fill: parent

                text: "Cancel"

                color: "#F2EFF8"

                font.family: Qt.application.font.family
                font.pixelSize: 9

                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        Rectangle {
            id: saveButton

            x: 280
            y: 522

            width: 148
            height: 31

            radius: 5

            border.width: 1
            border.color: "#CE3CFF"

            gradient: Gradient {
                orientation: Gradient.Horizontal

                GradientStop {
                    position: 0
                    color: "#C52FFF"
                }

                GradientStop {
                    position: 1
                    color: "#861CFF"
                }
            }

            Text {
                anchors.fill: parent

                text: "Save Settings"

                color: "#FFFFFF"

                font.family: Qt.application.font.family
                font.pixelSize: 9
                font.weight: Font.DemiBold

                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
