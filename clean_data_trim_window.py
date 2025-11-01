import os, glob
import pandas as pd
import numpy as np

# ================== CẤU HÌNH ==================
RAW_DIR = "gesture_data/"
CLEAN_DIR = "gesture_data_clean/"
SAMPLES_PER_WINDOW = 45
STEP_SIZE = 10
TRIM_THRESHOLD = 0.05         # Ngưỡng cắt phần tĩnh (càng nhỏ càng nhạy)
MIN_DYNAMIC_RATIO = 0.3       # Giữ lại ít nhất 30% dữ liệu
ENERGY_THRESHOLD = 0.02       # Ngưỡng loại bỏ cửa sổ tĩnh (nếu dùng sliding window)


# ================== HÀM ==================
def clean_dataframe(df):
    df = df.dropna(how="any")
    df = df.applymap(lambda x: str(x).replace('"', '').strip())
    df = df.apply(pd.to_numeric, errors="coerce").dropna(how="any")

    # Lọc giá trị ngoài dải
    df = df[(df["ax"].between(-20, 20)) &
            (df["ay"].between(-20, 20)) &
            (df["az"].between(-20, 20)) &
            (df["gx"].between(-500, 500)) &
            (df["gy"].between(-500, 500)) &
            (df["gz"].between(-500, 500))]
    return df


def trim_static_tail(data, threshold=TRIM_THRESHOLD, min_dynamic_ratio=MIN_DYNAMIC_RATIO):
    """Cắt phần đứng yên ở cuối"""
    diff = np.abs(np.diff(data, axis=0))
    motion = np.mean(diff, axis=1)
    active_idx = np.where(motion > threshold)[0]
    if len(active_idx) == 0:
        return data  # toàn bộ tĩnh
    last_motion = active_idx[-1]
    cut_idx = max(int(len(data) * min_dynamic_ratio), last_motion + 1)
    return data[:cut_idx]


def motion_energy(window):
    """Tính năng lượng chuyển động"""
    return np.mean(np.sqrt(np.sum(window**2, axis=1)))


def is_static_window(window, energy_threshold=ENERGY_THRESHOLD):
    """Kiểm tra cửa sổ có tĩnh hay không"""
    return motion_energy(window) < energy_threshold


def sliding_window(data, win=SAMPLES_PER_WINDOW, step=STEP_SIZE):
    """Tạo các cửa sổ dữ liệu chồng nhau"""
    return [data[i:i+win] for i in range(0, len(data)-win+1, step)]


# ================== XỬ LÝ TOÀN BỘ ==================
def preprocess_all():
    os.makedirs(CLEAN_DIR, exist_ok=True)
    files = glob.glob(os.path.join(RAW_DIR, "*.csv"))
    if not files:
        print("❌ Không tìm thấy file CSV trong gesture_data/")
        return

    total = 0
    for f in files:
        name = os.path.basename(f)
        try:
            label = int(name.split("_")[1])
        except:
            print(f"[BỎ QUA] {name} (tên file sai định dạng)")
            continue

        df = pd.read_csv(f)
        if not {"ax", "ay", "az", "gx", "gy", "gz"}.issubset(df.columns):
            print(f"[BỎ QUA] Sai cột: {name}")
            continue

        df = clean_dataframe(df)
        if len(df) < SAMPLES_PER_WINDOW:
            print(f"[CẢNH BÁO] {name} quá ngắn ({len(df)} mẫu)")
            continue

        # Cắt phần tĩnh cuối
        data_values = df[["ax", "ay", "az", "gx", "gy", "gz"]].values
        trimmed = trim_static_tail(data_values)

        # Nếu sau khi cắt quá ngắn → bỏ qua
        if len(trimmed) < SAMPLES_PER_WINDOW:
            print(f"[BỎ QUA] {name} (sau khi cắt còn {len(trimmed)} mẫu)")
            continue

        # (Tuỳ chọn) Lọc cửa sổ có năng lượng thấp
        windows = sliding_window(trimmed)
        active_windows = [w for w in windows if not is_static_window(w)]
        if not active_windows:
            print(f"[BỎ QUA] {name} (toàn bộ tĩnh sau cắt)")
            continue

        # Lấy lại dữ liệu ghép từ các cửa sổ động
        cleaned_data = np.concatenate(active_windows, axis=0)
        cleaned_df = pd.DataFrame(cleaned_data, columns=["ax","ay","az","gx","gy","gz"])

        # Ghi file sạch
        clean_path = os.path.join(CLEAN_DIR, name)
        cleaned_df.to_csv(clean_path, index=False)
        total += 1
        print(f"[OK] Lưu file sạch: {clean_path} ({len(cleaned_df)} mẫu)")

    print(f"\n✅ Đã xử lý xong {total} file vào thư mục {CLEAN_DIR}")


# ================== CHẠY ==================
if __name__ == "__main__":
    preprocess_all()
