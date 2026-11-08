#!/usr/bin/env python3
# encoding:utf-8
"""
TurboPi robot server: camera streaming + wheel control over ONE WebSocket.

  Pi -> Unity : binary JPEG frames (30 fps)
  Unity -> Pi : text JSON  {"fl":0.5,"fr":0.5,"rl":0.5,"rr":0.5}   (each -1..1)

Wheel mapping (from Hiwonder's MecanumChassis):
  M1 = left front, M2 = right front, M3 = left rear, M4 = right rear
  left motors (1, 3) are mounted mirrored, so their duty is negated.

Safety: if no drive message arrives for DRIVE_TIMEOUT seconds, or the client
disconnects, all motors are stopped.

Stop Hiwonder's stock program first (it owns the camera AND the serial port).

Run:        python3 pi_robot_server.py
Wheel test: python3 pi_robot_server.py --test     (put the robot on a block!)
"""
import asyncio
import json
import sys
import threading
import time

import cv2
import websockets

import struct

import serial   # pip3 install pyserial (already on the TurboPi image)

# --- minimal motor board (copied from Hiwonder's SDK, motors only) ------------
# Packet format: 0xAA 0x55 | function | length | data... | crc8
PACKET_FUNC_MOTOR = 3

CRC8_TABLE = [
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
    190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
    70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
    219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
    101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
    248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
    140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
    17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
    175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
    50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
    202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
    87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
    233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
    116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53
]


def checksum_crc8(data):
    check = 0
    for b in data:
        check = CRC8_TABLE[check ^ b]
    return check & 0x00FF


class MotorBoard:
    def __init__(self, device="/dev/ttyAMA0", baudrate=1000000, timeout=5):
        self.port = serial.Serial(None, baudrate, timeout=timeout)
        self.port.rts = False
        self.port.dtr = False
        self.port.setPort(device)
        self.port.open()

    def buf_write(self, func, data):
        buf = [0xAA, 0x55, int(func)]
        buf.append(len(data))
        buf.extend(data)
        buf.append(checksum_crc8(bytes(buf[2:])))
        self.port.write(bytes(buf))

    def set_motor_duty(self, dutys):
        """dutys = [[motor_number 1-4, duty], ...]"""
        data = [0x05, len(dutys)]
        for i in dutys:
            data.extend(struct.pack("<Bf", int(i[0] - 1), float(i[1])))
        self.buf_write(PACKET_FUNC_MOTOR, data)

# --- settings -----------------------------------------------------------------
PORT = 6767
CAMERA_INDEX = 0
WIDTH, HEIGHT = 640, 480
FPS = 30
JPEG_QUALITY = 70

MAX_DUTY = 40          # duty at full stick. Start low, raise gradually.
DRIVE_TIMEOUT = 0.5    # seconds without a drive message before stopping

T0 = time.monotonic()


def log(msg):
    print(f"[{time.monotonic() - T0:7.2f}s] {msg}", flush=True)


def fourcc_to_str(v):
    v = int(v)
    return "".join(chr((v >> (8 * i)) & 0xFF) for i in range(4))


class Stats:
    reads_ok = 0
    reads_failed = 0
    last_read_ms = 0.0
    frames_sent = 0
    bytes_sent = 0
    last_encode_ms = 0.0
    last_jpeg_bytes = 0
    clients = 0
    errors = 0


# --- wheels -------------------------------------------------------------------
class Drive:
    def __init__(self):
        self.board = MotorBoard()
        self.cmd = (0.0, 0.0, 0.0, 0.0)
        self.moving = False
        self.last_cmd_time = 0.0
        self.msgs = 0
        log("DRIVE: motor board opened")
        self.stop()

    def set_wheels(self, fl, fr, rl, rr):
        fl, fr, rl, rr = [max(-1.0, min(1.0, float(v))) for v in (fl, fr, rl, rr)]
        m = MAX_DUTY
        # left motors (1, 3) negated, same as Hiwonder's set_velocity
        self.board.set_motor_duty([[1, -fl * m], [2, fr * m], [3, -rl * m], [4, rr * m]])
        self.cmd = (fl, fr, rl, rr)
        self.moving = any(abs(v) > 0.001 for v in self.cmd)

    def stop(self):
        self.set_wheels(0, 0, 0, 0)

    def on_message(self, message):
        try:
            d = json.loads(message)
            self.set_wheels(d["fl"], d["fr"], d["rl"], d["rr"])
            self.last_cmd_time = time.monotonic()
            self.msgs += 1
            if self.msgs == 1:
                log(f"DRIVE: FIRST COMMAND received: {message}")
        except Exception as e:
            Stats.errors += 1
            log(f"DRIVE: bad message {message!r}: {e!r}")


# --- camera -------------------------------------------------------------------
class CameraStream:
    """Grabs frames in a background thread and keeps only the latest one."""

    def __init__(self):
        self.cap = None
        self.frame = None
        self.frame_time = 0.0
        self.running = True
        threading.Thread(target=self._task, daemon=True).start()

    def _open(self):
        log(f"CAMERA: opening index {CAMERA_INDEX} with CAP_V4L2...")
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
        log(f"CAMERA: isOpened() = {cap.isOpened()}")
        if not cap.isOpened():
            return cap
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, FPS)
        log("CAMERA: negotiated -> "
            f"fourcc={fourcc_to_str(cap.get(cv2.CAP_PROP_FOURCC))!r} "
            f"size={int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
            f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} "
            f"fps={cap.get(cv2.CAP_PROP_FPS)}")
        return cap

    def _task(self):
        fails = 0
        while self.running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    self.cap = self._open()
                    if not self.cap.isOpened():
                        self.cap = None
                        time.sleep(1)
                        continue

                t = time.monotonic()
                ret, img = self.cap.read()
                Stats.last_read_ms = (time.monotonic() - t) * 1000

                if ret:
                    if Stats.reads_ok == 0:
                        log(f"CAMERA: FIRST FRAME OK, shape={img.shape}")
                    Stats.reads_ok += 1
                    fails = 0
                    self.frame = cv2.resize(img, (WIDTH, HEIGHT),
                                            interpolation=cv2.INTER_NEAREST)
                    self.frame_time = time.monotonic()
                else:
                    Stats.reads_failed += 1
                    fails += 1
                    self.frame = None
                    if fails >= 10:
                        log("CAMERA: too many failed reads, reopening")
                        self.cap.release()
                        self.cap = None
                        fails = 0
                        time.sleep(0.5)
                    else:
                        time.sleep(0.05)
            except Exception as e:
                log(f"CAMERA: exception: {e!r}")
                time.sleep(0.5)

    def close(self):
        self.running = False
        time.sleep(0.2)
        if self.cap is not None:
            self.cap.release()


camera = None
drive = None


def encode(frame):
    t = time.monotonic()
    ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    Stats.last_encode_ms = (time.monotonic() - t) * 1000
    if not ok:
        log("ENCODE: imencode returned False!")
        return None
    data = jpg.tobytes()
    Stats.last_jpeg_bytes = len(data)
    return data


# --- network ------------------------------------------------------------------
async def send_frames(websocket):
    last = None
    first = True
    try:
        while True:
            start = time.monotonic()
            frame = camera.frame
            if frame is not None and frame is not last:
                last = frame
                data = await asyncio.to_thread(encode, frame)
                if data:
                    await websocket.send(data)
                    Stats.frames_sent += 1
                    Stats.bytes_sent += len(data)
                    if first:
                        log(f"NET: FIRST FRAME SENT ({len(data)} bytes)")
                        first = False
            await asyncio.sleep(max(0, 1 / FPS - (time.monotonic() - start)))
    except websockets.exceptions.ConnectionClosed:
        pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        Stats.errors += 1
        log(f"NET: send loop exception: {e!r}")


async def handle_connection(websocket):
    peer = getattr(websocket, "remote_address", "?")
    Stats.clients += 1
    log(f"NET: client connected from {peer} (clients: {Stats.clients})")
    sender = asyncio.create_task(send_frames(websocket))
    try:
        async for message in websocket:
            if isinstance(message, str):
                drive.on_message(message)
    except websockets.exceptions.ConnectionClosed as e:
        log(f"NET: client {peer} disconnected: {e}")
    except Exception as e:
        Stats.errors += 1
        log(f"NET: handler exception: {e!r}")
    finally:
        sender.cancel()
        drive.stop()
        Stats.clients -= 1
        log(f"NET: handler finished for {peer}; motors stopped (clients: {Stats.clients})")


async def watchdog():
    """Stops the wheels if Unity goes quiet while they are moving."""
    while True:
        await asyncio.sleep(0.1)
        if drive.moving and time.monotonic() - drive.last_cmd_time > DRIVE_TIMEOUT:
            log(f"DRIVE: no command for {DRIVE_TIMEOUT}s -> STOP")
            drive.stop()


async def stats_loop():
    prev = dict(ok=0, failed=0, sent=0, bytes=0, msgs=0)
    while True:
        await asyncio.sleep(1)
        age = (time.monotonic() - camera.frame_time) if camera.frame_time else -1
        c = drive.cmd
        log(
            "STATS | "
            f"cam: {Stats.reads_ok - prev['ok']:>2} fps, {Stats.reads_failed - prev['failed']:>2} failed, "
            f"age {age:4.2f}s | "
            f"net: clients={Stats.clients}, {Stats.frames_sent - prev['sent']:>2} fps sent, "
            f"{(Stats.bytes_sent - prev['bytes']) / 1024:6.1f} KB/s | "
            f"drive: {drive.msgs - prev['msgs']:>2} msg/s, "
            f"wheels fl={c[0]:+.2f} fr={c[1]:+.2f} rl={c[2]:+.2f} rr={c[3]:+.2f} | "
            f"errors={Stats.errors}"
        )
        prev = dict(ok=Stats.reads_ok, failed=Stats.reads_failed,
                    sent=Stats.frames_sent, bytes=Stats.bytes_sent, msgs=drive.msgs)


async def main():
    log(f"cv2 {cv2.__version__}, websockets {websockets.__version__}, MAX_DUTY={MAX_DUTY}")
    async with websockets.serve(handle_connection, "0.0.0.0", PORT):
        log(f"NET: listening on 0.0.0.0:{PORT}, waiting for Unity...")
        await asyncio.gather(watchdog(), stats_loop())


def self_test():
    steps = [
        ("FORWARD", (1, 1, 1, 1)),
        ("BACKWARD", (-1, -1, -1, -1)),
        ("STRAFE RIGHT", (1, -1, -1, 1)),
        ("STRAFE LEFT", (-1, 1, 1, -1)),
        ("SPIN (left side fwd, right side back)", (1, -1, 1, -1)),
    ]
    log("TEST: starting in 3 seconds. Robot should be on a block or clear of edges.")
    time.sleep(3)
    for name, w in steps:
        log(f"TEST: {name}  wheels={w}")
        drive.set_wheels(*w)
        time.sleep(1.0)
        drive.stop()
        time.sleep(0.8)
    log("TEST: done")


if __name__ == "__main__":
    drive = Drive()
    try:
        if "--test" in sys.argv:
            self_test()
        else:
            camera = CameraStream()
            asyncio.run(main())
    except KeyboardInterrupt:
        log("Stopped (Ctrl+C).")
    finally:
        drive.stop()
        if camera is not None:
            camera.close()