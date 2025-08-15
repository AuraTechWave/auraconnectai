from enum import Enum


class CheckInMethod(str, Enum):
    MANUAL = "manual"
    QR = "QR"
    FACE_ID = "faceID"
    FINGERPRINT = "fingerprint"
    PIN = "pin"
    RFID = "rfid"


class AttendanceStatus(str, Enum):
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    BREAK = "break"
    ABSENT = "absent"
    LATE = "late"
    EARLY_OUT = "early_out"
