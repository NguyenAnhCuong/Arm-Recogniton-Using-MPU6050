import socket
import csv
import time
import threading
from datetime import datetime

# ======================
# --- CẤU HÌNH ---
# ======================
HOST = "0.0.0.0"
PORT = 5000
SAMPLES_PER_GESTURE = 50
# GESTURE_LABELS = [ 1, 2, 3,4] #dung im,vay trai,vay phai, chat xuong,chat len
GESTURE_LABELS = [5, 6] #xoay trai,dam thang
TIMEOUT_SEC = 10  # chờ tối đa 10 giây khi thu dữ liệu


# ======================
# --- HÀM LƯU CSV ---
# ======================
def save_csv(rows, gesture_label):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gesture_{gesture_label}_{timestamp}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["label", "ax", "ay", "az", "gx", "gy", "gz"])
        writer.writerows(rows)
    print(f"[SAVE] Lưu {len(rows)} mẫu -> {filename}")


# ======================
# --- HÀM NHẬN DỮ LIỆU ---
# ======================
def receive_samples(conn, expected_count):
    conn.settimeout(TIMEOUT_SEC)
    rows = []
    start_time = time.time()

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            decoded = data.decode().strip()
            for line in decoded.split("\n"):
                if not line:
                    continue

                if line == "DONE":
                    print("[INFO] Nhận DONE từ ESP32")
                    return rows

                parts = line.split(",")
                if len(parts) == 7:
                    rows.append(parts)
                    print(f"[DATA] {line}")

                # Dừng nếu đủ số mẫu
                if len(rows) >= expected_count:
                    return rows

            # Timeout kiểm tra
            if time.time() - start_time > TIMEOUT_SEC:
                print("[WARN] Timeout! Dừng thu dữ liệu.")
                break
    except socket.timeout:
        print("[WARN] Hết thời gian chờ nhận dữ liệu.")
    except Exception as e:
        print("[ERROR]", e)

    return rows


# ======================
# --- HÀM CHÍNH ---
# ======================
def handle_client(conn, addr):
    print(f"[CONNECT] ESP32 kết nối từ {addr}")
    try:
        while True:
            cmd = input("\nNhấn 's' để bắt đầu thu dữ liệu (hoặc 'q' để thoát): ").lower()
            if cmd == "q":
                print("[EXIT] Dừng chương trình.")
                break
            elif cmd != "s":
                continue

            # Thu dữ liệu tự động cho các cử chỉ trong danh sách
            for gesture in GESTURE_LABELS:
                print(f"\n[GESTURE] === Thu cử chỉ {gesture} ===")
                conn.sendall(f"start {gesture}\n".encode())
                rows = receive_samples(conn, SAMPLES_PER_GESTURE)

                if rows:
                    save_csv(rows, gesture)
                else:
                    print("[WARN] Không nhận được dữ liệu cho cử chỉ", gesture)

            print("\n[INFO] ✅ Đã hoàn tất thu dữ liệu cho tất cả cử chỉ.")

    except Exception as e:
        print("[ERROR]", e)
    finally:
        conn.close()
        print("[DISCONNECT] ESP32 đã ngắt kết nối.")


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"[SERVER] Đang lắng nghe trên {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        client_thread = threading.Thread(target=handle_client, args=(conn, addr))
        client_thread.start()


if __name__ == "__main__":
    main()
