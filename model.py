import cv2
import mediapipe as mp
from math import hypot
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import numpy as np
import screen_brightness_control as sbc
from PyQt5 import QtWidgets, QtGui, QtCore
import sys
import pyautogui

class ControlWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Advanced Hand Gesture Control')
        self.setGeometry(300, 300, 500, 400)

        mainLayout = QtWidgets.QVBoxLayout()

        # Control options
        controlBox = QtWidgets.QGroupBox("Control Options")
        controlLayout = QtWidgets.QVBoxLayout()

        self.volumeCheckbox = QtWidgets.QCheckBox('Control Volume (Right Hand)')
        self.volumeCheckbox.setChecked(True)
        self.brightnessCheckbox = QtWidgets.QCheckBox('Control Brightness (Left Hand)')
        self.brightnessCheckbox.setChecked(True)
        self.mouseCheckbox = QtWidgets.QCheckBox('Control Mouse Pointer')

        controlLayout.addWidget(self.volumeCheckbox)
        controlLayout.addWidget(self.brightnessCheckbox)
        controlLayout.addWidget(self.mouseCheckbox)
        controlBox.setLayout(controlLayout)

        # Display options
        displayBox = QtWidgets.QGroupBox("Display Options")
        displayLayout = QtWidgets.QVBoxLayout()

        self.toggleGraphCheckbox = QtWidgets.QCheckBox('Show Hand Landmarks')
        self.toggleGraphCheckbox.setChecked(True)

        self.maximizeButton = QtWidgets.QPushButton('Maximize Video')
        self.maximizeButton.clicked.connect(self.toggleMaximize)
        self.isMaximized = False

        displayLayout.addWidget(self.toggleGraphCheckbox)
        displayLayout.addWidget(self.maximizeButton)
        displayBox.setLayout(displayLayout)

        # Fix control button
        self.fixButton = QtWidgets.QPushButton('Lock Control')
        self.fixButton.setCheckable(True)
        self.fixButton.clicked.connect(self.toggleFixButton)

        # Status display
        self.statusLabel = QtWidgets.QLabel("Status: Volume: 0% Brightness: 0%")
        self.statusLabel.setAlignment(QtCore.Qt.AlignCenter)

        # Add all widgets to main layout
        mainLayout.addWidget(controlBox)
        mainLayout.addWidget(displayBox)
        mainLayout.addWidget(self.fixButton)
        mainLayout.addWidget(self.statusLabel)

        self.setLayout(mainLayout)

        # Set window icon and styles
        self.setWindowIcon(QtGui.QIcon('hand_icon.png'))
        self.setStyleSheet("""
            QWidget {
                font-size: 14px;
                font-family: Arial, sans-serif;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid gray;
                border-radius: 5px;
                margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3e8e41;
            }
            QPushButton:checked {
                background-color: #f44336;
            }
            QPushButton:checked:hover {
                background-color: #d32f2f;
            }
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #999;
                background: white;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #555;
            }
            QLabel {
                font-size: 16px;
                color: #333;
            }
        """)

        self.show()

    def toggleMaximize(self):
        self.isMaximized = not self.isMaximized
        self.maximizeButton.setText('Minimize Video' if self.isMaximized else 'Maximize Video')

    def toggleFixButton(self):
        if self.fixButton.isChecked():
            self.fixButton.setText('Unlock Control')
        else:
            self.fixButton.setText('Lock Control')

    def updateStatus(self, volume, brightness):
        self.statusLabel.setText(f"Status: Volume: {volume}% Brightness: {brightness}%")

class HandControl:
    def __init__(self, gui):
        self.gui = gui
        self.cap = cv2.VideoCapture(0)
        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mpDraw = mp.solutions.drawing_utils

        # Setup audio control
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)

        self.volume = cast(interface, POINTER(IAudioEndpointVolume))
        self.volMin, self.volMax = self.volume.GetVolumeRange()[:2]

        self.brightnessMin, self.brightnessMax = 0, 100
        self.screenWidth, self.screenHeight = pyautogui.size()

        self.currentVolume = int(np.interp(self.get_current_volume(), [self.volMin, self.volMax], [0, 100]))
        self.currentBrightness = sbc.get_brightness()[0]

    def get_current_volume(self):
        return self.volume.GetMasterVolumeLevel()

    def run(self):
        while True:
            success, img = self.cap.read()
            if not success:
                print("Failed to capture frame. Exiting...")
                break

            img = cv2.flip(img, 1)
            imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.hands.process(imgRGB)

            leftHand, rightHand = None, None
            if results.multi_hand_landmarks:
                for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                    if handedness.classification[0].label == "Left":
                        leftHand = hand_landmarks
                    else:
                        rightHand = hand_landmarks

                    if self.gui.toggleGraphCheckbox.isChecked():
                        self.mpDraw.draw_landmarks(img, hand_landmarks, self.mpHands.HAND_CONNECTIONS)

            if not self.gui.fixButton.isChecked():
                if leftHand and self.gui.brightnessCheckbox.isChecked():
                    self.currentBrightness = self.control_brightness(img, leftHand)
                if rightHand and self.gui.volumeCheckbox.isChecked():
                    self.currentVolume = self.control_volume(img, rightHand)
                if (leftHand or rightHand) and self.gui.mouseCheckbox.isChecked():
                    self.control_mouse(img, leftHand or rightHand)

            self.gui.updateStatus(self.currentVolume, self.currentBrightness)

            if self.gui.isMaximized:
                cv2.namedWindow('Hand Control', cv2.WND_PROP_FULLSCREEN)
                cv2.setWindowProperty('Hand Control', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.namedWindow('Hand Control', cv2.WINDOW_NORMAL)
                cv2.resizeWindow('Hand Control', 1280, 720)

            cv2.imshow('Hand Control', img)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):
                break
            elif key == ord('f'):
                self.gui.toggleMaximize()

        self.cap.release()
        cv2.destroyAllWindows()

    def control_brightness(self, img, hand_landmarks):
        x1, y1 = hand_landmarks.landmark[4].x, hand_landmarks.landmark[4].y
        x2, y2 = hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y
        length = hypot(x2 - x1, y2 - y1)
        brightness = np.interp(length, [0.1, 0.5], [self.brightnessMin, self.brightnessMax])
        brightness = int(brightness)
        sbc.set_brightness(brightness)
        cv2.putText(img, f"Brightness: {brightness}%", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        return brightness

    def control_volume(self, img, hand_landmarks):
        x1, y1 = hand_landmarks.landmark[4].x, hand_landmarks.landmark[4].y
        x2, y2 = hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y
        length = hypot(x2 - x1, y2 - y1)
        vol = np.interp(length, [0.1, 0.5], [self.volMin, self.volMax])
        self.volume.SetMasterVolumeLevel(vol, None)
        volPer = int(np.interp(vol, [self.volMin, self.volMax], [0, 100]))
        cv2.putText(img, f"Volume: {volPer}%", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        return volPer

    def control_mouse(self, img, hand_landmarks):
        x1, y1 = hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y
        screenX = np.interp(x1, [0, 1], [0, self.screenWidth])
        screenY = np.interp(y1, [0, 1], [0, self.screenHeight])
        pyautogui.moveTo(screenX, screenY)
        cv2.putText(img, f"Mouse: ({int(screenX)}, {int(screenY)})", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    gui = ControlWindow()
    handControl = HandControl(gui)
    handControl.run()
    sys.exit(app.exec_())