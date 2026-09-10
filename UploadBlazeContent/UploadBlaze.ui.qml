import QtQuick
import QtQuick.Controls

Item {
    id: form
    property var fileModel: []
    property bool busy: false
    property string bucketName: "No bucket selected"
    property string connectionText: "Not checked"
    property string statusText: "Ready"
    property real progressValue: 0
    property string activityText: ""
    property bool showPassword: false
    property alias password: passwordInput.text
    property alias confirmation: confirmationInput.text
    property alias fileList: fileListView
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

        color: "#1B2026"

        border.width: 1
        border.color: "#49515E"

        antialiasing: true
        clip: true

        // =========================================================
        // BACKGROUND
        // =========================================================

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
            id: logo

            x: 11
            y: 12

            width: 30
            height: 25

            source: "assets/cloud-logo.svg"

            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
        }

        Text {
            id: appTitle

            x: 44
            y: 6

            width: 160
            height: 23

            text: "UploadBlaze"

            color: "#F2F0FF"

            font.family: Qt.application.font.family
            font.pixelSize: 16
            font.weight: Font.DemiBold

            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
        }

        Text {
            x: 44
            y: 25

            width: 190
            height: 17

            text: "Prepare. Protect. Back up."

            color: "#B4B7CA"

            font.family: Qt.application.font.family
            font.pixelSize: 10

            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
        }

        Rectangle {
            id: settingsButton

            x: 318
            y: 11

            width: 72
            height: 28

            radius: 4

            color: "#252A34"

            border.width: 1
            border.color: "#7480B8"

            Image {
                x: 9
                y: 7

                width: 14
                height: 14

                source: "assets/settings.svg"

                fillMode: Image.PreserveAspectFit
            }

            Text {
                x: 28
                y: 0

                width: 41
                height: 28

                text: "Settings"

                color: "#F2F1FA"

                font.family: Qt.application.font.family
                font.pixelSize: 9

                verticalAlignment: Text.AlignVCenter
            }
        }

        Image {
            x: 403
            y: 14

            width: 18
            height: 13

            source: "assets/minimize.svg"
        }

        Image {
            x: 428
            y: 11

            width: 17
            height: 17

            source: "assets/close.svg"
        }

        // =========================================================
        // BACKBLAZE CONNECTION BAR
        // =========================================================

        Rectangle {
            id: connectionBar

            x: 10
            y: 54

            width: 435
            height: 35

            radius: 5

            color: "#20252C"

            border.width: 1
            border.color: "#444C58"

            Image {
                x: 9
                y: 7

                width: 16
                height: 21

                source: "assets/backblaze.svg"

                fillMode: Image.PreserveAspectFit
            }

            Text {
                x: 34
                y: 0

                width: 80
                height: 35

                text: "Backblaze B2"

                color: "#ECEAF5"

                font.family: Qt.application.font.family
                font.pixelSize: 10

                verticalAlignment: Text.AlignVCenter
            }

            Rectangle {
                x: 111
                y: 8

                width: 1
                height: 19

                color: "#747B86"
            }

            Text {
                x: 120
                y: 0

                width: 180
                height: 35

                text: form.bucketName
                elide: Text.ElideMiddle

                color: "#B0B3C4"

                font.family: Qt.application.font.family
                font.pixelSize: 9

                verticalAlignment: Text.AlignVCenter
            }

            Rectangle {
                x: 365
                y: 14

                width: 7
                height: 7

                radius: 3.5

                color: "#9299AA"
            }

            Text {
                x: 377
                y: 0

                width: 54
                height: 35

                text: form.connectionText

                color: "#B5B8C7"

                font.family: Qt.application.font.family
                font.pixelSize: 8

                verticalAlignment: Text.AlignVCenter
            }
        }

        // =========================================================
        // FILES PANEL
        // =========================================================

        Rectangle {
            id: filesPanel

            x: 10
            y: 97

            width: 435
            height: 175

            radius: 6

            color: "#1C2127"

            border.width: 1
            border.color: "#444C58"

            Text {
                x: 10
                y: 6

                width: 50
                height: 21

                text: "Files"

                color: "#F2EFFA"

                font.family: Qt.application.font.family
                font.pixelSize: 11
                font.weight: Font.DemiBold

                verticalAlignment: Text.AlignVCenter
            }

            Rectangle {
                id: addFilesButton

                x: 54
                y: 5

                width: 69
                height: 22

                radius: 4

                color: "#262631"

                border.width: 1
                border.color: "#A053FF"

                Image {
                    x: 8
                    y: 5

                    width: 12
                    height: 12

                    source: "assets/plus.svg"
                }

                Text {
                    x: 25
                    y: 0

                    width: 42
                    height: 22

                    text: "Add Files"

                    color: "#EEEAF7"

                    font.family: Qt.application.font.family
                    font.pixelSize: 9

                    verticalAlignment: Text.AlignVCenter
                }
            }

            Text {
                x: 391
                y: 5

                width: 31
                height: 22

                text: form.fileModel.length + " files"

                color: "#EEEAF7"

                font.family: Qt.application.font.family
                font.pixelSize: 9

                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
            }

            Image {
                x: 7
                y: 32

                width: 421
                height: 36

                source: "assets/drop-border.svg"

                fillMode: Image.Stretch
            }

            Image {
                x: 151
                y: 41

                width: 13
                height: 16

                source: "assets/file.svg"
            }

            Text {
                x: 171
                y: 34

                width: 190
                height: 32

                text: "Drop files or ZIP archives here"

                color: "#DADAE4"

                font.family: Qt.application.font.family
                font.pixelSize: 9

                verticalAlignment: Text.AlignVCenter
            }

            // TABLE HEADER

            Rectangle {
                x: 0
                y: 74

                width: 435
                height: 21

                color: "#252B33"
            }

            Rectangle {
                x: 198
                y: 74

                width: 1
                height: 101

                color: "#343A43"
            }

            Rectangle {
                x: 275
                y: 74

                width: 1
                height: 101

                color: "#343A43"
            }

            Rectangle {
                x: 406
                y: 74

                width: 1
                height: 101

                color: "#343A43"
            }

            Text {
                x: 9
                y: 74
                width: 160
                height: 21

                text: "Name"

                color: "#C8CBD7"

                font.family: Qt.application.font.family
                font.pixelSize: 8

                verticalAlignment: Text.AlignVCenter
            }

            Text {
                x: 206
                y: 74
                width: 60
                height: 21

                text: "Size"

                color: "#C8CBD7"

                font.family: Qt.application.font.family
                font.pixelSize: 8

                verticalAlignment: Text.AlignVCenter
            }

            Text {
                x: 284
                y: 74
                width: 100
                height: 21

                text: "Status"

                color: "#C8CBD7"

                font.family: Qt.application.font.family
                font.pixelSize: 8

                verticalAlignment: Text.AlignVCenter
            }

            FileList {
                id: fileListView
                x: 0; y: 95; width: 435; height: 80
                entries: form.fileModel
                busy: form.busy
            }
        }

        // =========================================================
        // FILE PROTECTION
        // =========================================================

        Rectangle {
            id: protectionPanel

            x: 10
            y: 282

            width: 435
            height: 96

            radius: 6

            color: "#1D2228"

            border.width: 1
            border.color: "#444C58"

            Text {
                x: 10
                y: 5

                width: 150
                height: 20

                text: "File Protection"

                color: "#F3F1FA"

                font.family: Qt.application.font.family
                font.pixelSize: 11
                font.weight: Font.DemiBold
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                x: 10
                y: 25

                width: 150
                height: 17

                text: "Encryption Password"

                color: "#D9D8E5"

                font.family: Qt.application.font.family
                font.pixelSize: 8
            }

            Text {
                x: 224
                y: 25

                width: 150
                height: 17

                text: "Confirm Password"

                color: "#D9D8E5"

                font.family: Qt.application.font.family
                font.pixelSize: 8
            }

            Rectangle {
                x: 10
                y: 41

                width: 200
                height: 27

                radius: 4

                color: "#20252B"

                border.width: 1
                border.color: "#737E99"

                TextField {
                    id: passwordInput
                    objectName: "passwordInput"
                    readOnly: form.busy
                    selectByMouse: true
                    echoMode: form.showPassword ? TextInput.Normal : TextInput.Password
                    inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                    background: null
                    padding: 0
                    placeholderTextColor: "#9EA3B2"
                    color: "#ECEAF4"
                    x: 8
                    y: 0
                    width: 160
                    height: 27

                    text: ""
                    placeholderText: "Enter a password"

                    font.family: Qt.application.font.family
                    font.pixelSize: 8
                    verticalAlignment: Text.AlignVCenter
                }

                Image {
                    x: 181
                    y: 8
                    width: 12
                    height: 11
                    source: "assets/eye.svg"
                }
            }

            Rectangle {
                x: 224
                y: 41

                width: 201
                height: 27

                radius: 4

                color: "#20252B"

                border.width: 1
                border.color: "#737E99"

                TextField {
                    id: confirmationInput
                    objectName: "confirmationInput"
                    readOnly: form.busy
                    selectByMouse: true
                    echoMode: form.showPassword ? TextInput.Normal : TextInput.Password
                    inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                    background: null
                    padding: 0
                    placeholderTextColor: "#9EA3B2"
                    color: "#ECEAF4"
                    x: 8
                    y: 0
                    width: 160
                    height: 27

                    text: ""
                    placeholderText: "Repeat password"

                    font.family: Qt.application.font.family
                    font.pixelSize: 8
                    verticalAlignment: Text.AlignVCenter
                }

                Image {
                    x: 181
                    y: 8
                    width: 12
                    height: 11
                    source: "assets/eye.svg"
                }
            }

            Text {
                x: 10
                y: 72

                width: 260
                height: 15

                text: "Open .7z backups with 7-Zip or The Unarchiver."

                color: "#AFB3C4"

                font.family: Qt.application.font.family
                font.pixelSize: 7
            }
        }

        // =========================================================
        // ACTION BUTTONS
        // =========================================================

        Rectangle {
            x: 10
            y: 387
            width: 100
            height: 37

            radius: 5
            color: "#252A33"

            border.width: 1
            border.color: "#7480AC"

            Image {
                x: 23
                y: 10
                width: 15
                height: 17
                source: "assets/archive.svg"
            }

            Text {
                x: 45
                y: 0
                width: 50
                height: 37

                text: "Zip Files"

                color: "#EEEAF6"

                font.family: Qt.application.font.family
                font.pixelSize: 9

                verticalAlignment: Text.AlignVCenter
            }
        }

        Rectangle {
            x: 116
            y: 387
            width: 111
            height: 37

            radius: 5
            color: "#252A33"

            border.width: 1
            border.color: "#7480AC"

            Image {
                x: 21
                y: 10
                width: 16
                height: 17
                source: "assets/shield.svg"
            }

            Text {
                x: 44
                y: 0
                width: 65
                height: 37

                text: "Protect Files"

                color: "#EEEAF6"

                font.family: Qt.application.font.family
                font.pixelSize: 9

                verticalAlignment: Text.AlignVCenter
            }
        }

        Rectangle {
            id: uploadBackupButton

            x: 233
            y: 387

            width: 133
            height: 37

            radius: 5

            border.width: 1
            border.color: "#CB42FF"

            gradient: Gradient {
                orientation: Gradient.Horizontal

                GradientStop {
                    position: 0
                    color: "#C02BFF"
                }

                GradientStop {
                    position: 1
                    color: "#861DFF"
                }
            }

            Image {
                x: 23
                y: 9
                width: 18
                height: 18
                source: "assets/upload.svg"
            }

            Text {
                x: 49
                y: 0
                width: 79
                height: 37

                text: "Upload Backup"

                color: "#FFFFFF"

                font.family: Qt.application.font.family
                font.pixelSize: 9

                verticalAlignment: Text.AlignVCenter
            }
        }

        Rectangle {
            x: 372
            y: 387
            width: 73
            height: 37

            radius: 5

            color: "#252326"

            border.width: 1
            border.color: "#AD5660"

            Rectangle {
                x: 18
                y: 13

                width: 10
                height: 10

                radius: 1

                color: "#DE8A93"
            }

            Text {
                x: 36
                y: 0
                width: 34
                height: 37

                text: "Stop"

                color: "#E18A94"

                font.family: Qt.application.font.family
                font.pixelSize: 9

                verticalAlignment: Text.AlignVCenter
            }
        }

        // =========================================================
        // PROGRESS
        // =========================================================

        Text {
            x: 10
            y: 432

            width: 385
            height: 17

            text: form.statusText
            elide: Text.ElideRight

            color: "#ECEAF4"

            font.family: Qt.application.font.family
            font.pixelSize: 8
        }

        Text {
            x: 412
            y: 432

            width: 33
            height: 17

            text: form.progressValue < 0 ? "…" : Math.floor(form.progressValue) + "%"

            color: "#ECEAF4"

            font.family: Qt.application.font.family
            font.pixelSize: 8

            horizontalAlignment: Text.AlignRight
        }

        Rectangle {
            x: 10
            y: 452

            width: 435
            height: 9

            radius: 4.5

            color: "#333946"

            border.width: 1
            border.color: "#727C94"
            Rectangle {
                x: 1; y: 1
                width: Math.max(0, (parent.width - 2) * form.progressValue / 100)
                height: parent.height - 2
                radius: 3.5
                color: "#9854FF"
            }
        }

        // =========================================================
        // ACTIVITY LOG
        // =========================================================

        Rectangle {
            x: 10
            y: 483

            width: 435
            height: 59

            radius: 6

            color: "#1D2228"

            border.width: 1
            border.color: "#444C58"

            Rectangle {
                x: 1
                y: 1
                width: 433
                height: 28

                radius: 5

                color: "#1F242B"
            }

            Rectangle {
                x: 1
                y: 21
                width: 433
                height: 8

                color: "#1F242B"
            }

            Image {
                x: 9
                y: 9
                width: 10
                height: 9
                source: "assets/activity-chevron.svg"
            }

            Text {
                x: 25
                y: 0
                width: 100
                height: 29

                text: "Activity Log"

                color: "#EFEAF7"

                font.family: Qt.application.font.family
                font.pixelSize: 9
                font.weight: Font.DemiBold

                verticalAlignment: Text.AlignVCenter
            }

            Image {
                x: 395
                y: 8

                width: 12
                height: 13

                source: "assets/trash.svg"
            }

            Text {
                x: 409
                y: 0

                width: 20
                height: 29

                text: "Clear"

                color: "#D0CFDC"

                font.family: Qt.application.font.family
                font.pixelSize: 7

                verticalAlignment: Text.AlignVCenter
            }

            Rectangle {
                x: 0
                y: 28
                width: 435
                height: 1
                color: "#3A4049"
            }

            ActivityView {
                x: 10; y: 33; width: 415; height: 23
                logText: form.activityText
            }
        }

        // =========================================================
        // FOOTER
        // =========================================================

        Text {
            x: 10
            y: 548

            width: 220
            height: 14

            text: "Original files are kept unchanged."

            color: "#A3A8BA"

            font.family: Qt.application.font.family
            font.pixelSize: 6
        }
    }
}
