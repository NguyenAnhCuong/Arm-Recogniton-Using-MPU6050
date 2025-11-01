import socket
import threading
import time
import numpy as np
import pandas as pd
import joblib
import json
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences
import keyboard
import csv
from datetime import datetime
import os
import sys

# ============================================================
# --- CẤU HÌNH ---
# ============================================================
HOST = "0.0.0.0"
DATA_PORT = 5000
LED_PORT = 6000
TIMEOUT_SECONDS = 5

MODEL_PATH = "./gesture_model_lstm.h5"
SCALER_PATH = "./scaler.joblib"
CONFIG_PATH = "./model_config.json"

SAVE_RAW_DATA = True
SAVE_DIR = "./logs/"
CONFIDENCE_THRESHOLD = 0.9

# ============================================================
# --- TẢI MODEL ---
# ============================================================
print("[*] Đang tải model và scaler...", flush=True)
model = load_model(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

max_len = config["max_len"]
n_features = config["n_features"]
print(f"[*] Model sẵn sàng (max_len={max_len}, n_features={n_features})", flush=True)

# ============================================================
# --- BIẾN TRẠNG THÁI ---
# ============================================================
collecting = False
data_buffer = []
last_data_time = 0

sensor_conn = None
sensor_addr = None

led_client_socket = None
led_client_addr = None

lock = threading.Lock()

# ============================================================
# --- GỬI LỆNH ĐIỀU KHIỂN LED ---
# ============================================================
def send_led_command(command):
    global led_client_socket, led_client_addr
    with lock:
        if led_client_socket is None:
            print(f"[LED] ⚠️ Chưa có thiết bị LED kết nối, không thể gửi lệnh {command}", flush=True)
            return

        try:
            led_client_socket.sendall(f"{command}\n".encode())
            print(f"[LED] → Gửi lệnh {command} tới {led_client_addr}", flush=True)
        except Exception as e:
            print(f"[LED] ⚠️ Lỗi gửi lệnh: {e}", flush=True)
            try:
                led_client_socket.close()
            except:
                pass
            led_client_socket = None

# ============================================================
# --- HÀM LƯU CSV ---
# ============================================================
def save_csv(rows, predicted_label=None):
    if not rows:
        print("[SAVE] Không có dữ liệu để lưu.", flush=True)
        return

    os.makedirs(SAVE_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{SAVE_DIR}gesture_{timestamp}.csv"

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["label", "ax", "ay", "az", "gx", "gy", "gz"])
        label = predicted_label if predicted_label is not None else ""
        for row in rows:
            writer.writerow([label] + row)

    print(f"[SAVE] Đã lưu {len(rows)} mẫu vào {filename}", flush=True)

# ============================================================
# --- HÀM DỰ ĐOÁN ---
# ============================================================
def process_and_predict(data):
    df = pd.DataFrame(data, columns=['ax', 'ay', 'az', 'gx', 'gy', 'gz'])
    if len(df) == 0:
        print("[WARNING] Không có dữ liệu để dự đoán.", flush=True)
        return

    seq = df.values.astype('float32')
    seq_padded = pad_sequences([seq], maxlen=max_len, padding='post', dtype='float32')

    seq_2d = seq_padded.reshape(-1, n_features)
    seq_scaled = scaler.transform(seq_2d)
    seq_scaled_3d = seq_scaled.reshape(1, max_len, n_features)

    preds = model.predict(seq_scaled_3d)
    label = int(np.argmax(preds))
    confidence = float(np.max(preds))

    print(f"\n[RESULT] → Cử chỉ dự đoán: {label} (Độ tin cậy: {confidence*100:.2f}%)", flush=True)

    # --- GỬI LỆNH LED ---
    if confidence >= 0.5:
        if label == 1:
            send_led_command("LED_ON")
        elif label == 2:
            send_led_command("LED_OFF")
        elif label == 3:
            send_led_command("BUZZER_ON")
        elif label == 0:
            send_led_command("BUZZER_OFF")
        elif label == 5:
            send_led_command("FAN_ON")
        elif label == 6:
            send_led_command("FAN_OFF")
        elif label == 4:
            send_led_command("LCD_COUNTDOWN")


    # --- LƯU CSV ---
    if SAVE_RAW_DATA:
        if confidence >= CONFIDENCE_THRESHOLD:
            save_csv(data, predicted_label=label)
        else:
            save_csv(data, predicted_label=None)

    # --- Sau khi dự đoán xong → Thoát chương trình ---
    print("\n[EXIT] Dự đoán xong. Thoát chương trình...", flush=True)
    time.sleep(2)
    os._exit(0)

# ============================================================
# --- XỬ LÝ DỮ LIỆU ---
# ============================================================
def handle_sensor_client(conn, addr):
    global collecting, data_buffer, last_data_time, sensor_conn, sensor_addr
    with lock:
        sensor_conn = conn
        sensor_addr = addr
    print(f"[+] Kết nối từ ESP32 (sensor): {addr}", flush=True)

    buffer = ""
    try:
        while True:
            data = conn.recv(1024).decode("utf-8")
            if not data:
                break
            buffer += data

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                print(f"[DATA] {line}", flush=True)

                if line.upper() == "DONE":
                    print("[INFO] Nhận DONE từ ESP32 (sensor).", flush=True)
                    collecting = False
                    process_and_predict(data_buffer)
                    data_buffer = []
                    continue

                if collecting:
                    try:
                        parts = line.split(",")
                        if len(parts) >= 7:
                            _, ax, ay, az, gx, gy, gz = parts[-7:]
                        else:
                            continue

                        row = [float(ax), float(ay), float(az),
                               float(gx), float(gy), float(gz)]
                        data_buffer.append(row)
                        last_data_time = time.time()
                    except Exception as e:
                        print(f"[WARNING] Lỗi xử lý dòng: {line} → {e}", flush=True)
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
    finally:
        try:
            conn.close()
        except:
            pass
        with lock:
            sensor_conn = None
            sensor_addr = None
        print(f"[-] Ngắt kết nối với ESP32 (sensor) {addr}", flush=True)

# ============================================================
# --- XỬ LÝ LED CLIENT ---
# ============================================================
def handle_led_client(conn, addr):
    global led_client_socket, led_client_addr
    with lock:
        led_client_socket = conn
        led_client_addr = addr
    print(f"[+] ESP32 (LED) kết nối từ {addr}", flush=True)

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            text = data.decode(errors='ignore').strip()
            if text:
                print(f"[LED <- device] {addr}: {text}", flush=True)
    except Exception as e:
        print(f"[LED] Lỗi kết nối từ {addr}: {e}", flush=True)
    finally:
        with lock:
            try:
                led_client_socket.close()
            except:
                pass
            led_client_socket = None
            led_client_addr = None
        print(f"[-] ESP32 (LED) ngắt kết nối {addr}", flush=True)

# ============================================================
# --- LẮNG NGHE PHÍM NHẤN ---
# ============================================================
def keyboard_listener():
    global collecting, data_buffer, last_data_time, sensor_conn
    print("[*] Nhấn 's' để bắt đầu thu dữ liệu.", flush=True)
    while True:
        if sensor_conn is None:
            time.sleep(0.5)
            continue

        try:
            if keyboard.is_pressed('s') and not collecting:
                print(f"[CMD] Gửi lệnh start tới ESP32 (sensor)...", flush=True)
                try:
                    sensor_conn.sendall(f"start 0\n".encode())
                    data_buffer = []
                    collecting = True
                    last_data_time = time.time()
                except Exception as e:
                    print(f"[CMD] Lỗi gửi lệnh start: {e}", flush=True)
                time.sleep(1)
        except OSError:
            time.sleep(1)

# ============================================================
# --- SERVER LED ---
# ============================================================
def led_server_loop():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, LED_PORT))
    s.listen(1)
    print(f"[*] Server LED đang chạy tại {HOST}:{LED_PORT}", flush=True)
    while True:
        conn, addr = s.accept()
        t = threading.Thread(target=handle_led_client, args=(conn, addr), daemon=True)
        t.start()

# ============================================================
# --- MAIN SERVER ---
# ============================================================
def start_server():
    threading.Thread(target=led_server_loop, daemon=True).start()
    threading.Thread(target=keyboard_listener, daemon=True).start()

    while True:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, DATA_PORT))
        server.listen(1)
        print(f"[*] Server TCP (data) đang chạy tại {HOST}:{DATA_PORT}", flush=True)
        print("[*] Đang chờ ESP32 (sensor) kết nối...", flush=True)

        try:
            conn, addr = server.accept()
            threading.Thread(target=handle_sensor_client, args=(conn, addr), daemon=True).start()
            while True:
                time.sleep(1)
        except Exception as e:
            print(f"[MAIN] Lỗi server data: {e}", flush=True)
        finally:
            try:
                server.close()
            except:
                pass
        time.sleep(1)

if __name__ == "__main__":
    start_server()
