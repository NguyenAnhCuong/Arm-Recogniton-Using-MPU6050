import os, glob, json, joblib
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Masking
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.preprocessing.sequence import pad_sequences

# ================== CẤU HÌNH ==================
DATA_DIR = "gesture_data_clean/"
MODEL_SAVE_PATH = "gesture_model_lstm.h5"
SCALER_SAVE_PATH = "scaler.joblib"
CONFIG_SAVE_PATH = "model_config.json"
SAMPLES_PER_WINDOW = 45
STEP_SIZE = 10
EPOCHS = 50

# ================== HÀM SLIDING WINDOW ==================
def sliding_window(data, win=45, step=10):
    return [data[i:i+win] for i in range(0, len(data)-win+1, step)]

# ================== ĐỌC DỮ LIỆU ==================
files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
if not files:
    raise RuntimeError("❌ Không có dữ liệu trong gesture_data_clean/. Hãy chạy preprocess_data.py trước!")

X, y = [], []
for f in files:
    label = int(os.path.basename(f).split("_")[1])
    df = pd.read_csv(f)
    if len(df) < SAMPLES_PER_WINDOW:
        continue
    for seq in sliding_window(df[["ax","ay","az","gx","gy","gz"]].values, SAMPLES_PER_WINDOW, STEP_SIZE):
        X.append(seq)
        y.append(label)

print(f"✅ Thu được {len(X)} chuỗi hợp lệ từ {len(files)} file")

X = pad_sequences(X, padding="post", dtype="float32")
max_len, n_feat = X.shape[1], X.shape[2]
y = np.array(y)
y_cat = to_categorical(y)
n_class = y_cat.shape[1]

import collections
counter = collections.Counter(y)
print("\n📊 Phân bố số mẫu mỗi lớp:")
for label, count in sorted(counter.items()):
    print(f"Lớp {label}: {count} mẫu")


# ================== CHUẨN HÓA ==================
scaler = StandardScaler()
X_2d = X.reshape(-1, n_feat)
scaler.fit(X_2d)
X_scaled = scaler.transform(X_2d).reshape(X.shape)

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y_cat, test_size=0.2, random_state=42, stratify=y
)

# ================== TẠO MÔ HÌNH LSTM ==================
model = Sequential([
    Masking(mask_value=0.0, input_shape=(max_len, n_feat)),
    LSTM(128, return_sequences=True),
    Dropout(0.3),
    LSTM(64),
    Dropout(0.3),
    Dense(64, activation="relu"),
    Dense(n_class, activation="softmax")
])

model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
model.summary()

# ================== HUẤN LUYỆN ==================
print("\n🚀 Bắt đầu huấn luyện ...")
history = model.fit(
    X_train, y_train,
    epochs=EPOCHS, batch_size=64,
    validation_data=(X_test, y_test),
    verbose=1
)

# ================== ĐÁNH GIÁ ==================
loss, acc = model.evaluate(X_test, y_test, verbose=0)
print(f"\n✅ Accuracy kiểm thử: {acc*100:.2f}%")

# --- Confusion Matrix ---
y_pred = np.argmax(model.predict(X_test), axis=1)
y_true = np.argmax(y_test, axis=1)
cm = confusion_matrix(y_true, y_pred)
ConfusionMatrixDisplay(cm, display_labels=sorted(set(y_true))).plot(cmap="Blues")
plt.title("Confusion Matrix - Gesture Recognition (LSTM)")
plt.show()

# --- Vẽ quá trình huấn luyện ---
plt.figure()
plt.plot(history.history['accuracy'], label='Train Acc')
plt.plot(history.history['val_accuracy'], label='Val Acc')
plt.legend(), plt.title("Training Accuracy"), plt.show()

# ================== LƯU MODEL ==================
model.save(MODEL_SAVE_PATH)
joblib.dump(scaler, SCALER_SAVE_PATH)
with open(CONFIG_SAVE_PATH, "w") as f:
    json.dump({"max_len": max_len, "n_features": n_feat}, f)

print("\n💾 Model, scaler và config đã được lưu.")
