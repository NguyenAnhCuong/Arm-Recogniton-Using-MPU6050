#include <WiFi.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>

// ========================
// --- CẤU HÌNH MẠNG ---
// ========================
const char* ssid = "Onepiece";
const char* password = "12345678";

const char* serverIP = "10.184.254.142";  // IP máy tính chạy server Python
const uint16_t serverPort = 5000;

WiFiClient client;
Adafruit_MPU6050 mpu;

const int SAMPLE_COUNT = 50;
const int COLLECTION_INTERVAL_MS = 50;

bool isCollecting = false;
int currentSample = 0;
int gestureLabel = 0;
unsigned long lastSampleTime = 0;
unsigned long lastPingTime = 0;   // Thời điểm gửi ping gần nhất

// ========================
// --- KẾT NỐI WIFI ---
// ========================
void connectWiFi() {
  Serial.printf("Connecting to %s", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi Connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

// ========================
// --- KẾT NỐI TỚI SERVER ---
// ========================
bool connectServer() {
  Serial.printf("[WiFi] Kết nối tới server %s:%d...\n", serverIP, serverPort);

  if (client.connected()) {
    client.stop();
    delay(200);
  }

  if (client.connect(serverIP, serverPort)) {
    Serial.println("✅ Kết nối server thành công!");
    client.setTimeout(5); // timeout đọc 5s
    return true;
  } else {
    Serial.println("❌ Kết nối server thất bại!");
    return false;
  }
}

// ========================
// --- BẮT ĐẦU THU ---
// ========================
void startCollection(int gesture) {
  Serial.printf("\n[ESP] Chuẩn bị thu cử chỉ %d trong 3s...\n", gesture);
  for (int c = 3; c > 0; c--) {
    Serial.printf("...%d\n", c);
    delay(1000);
  }

  isCollecting = true;
  currentSample = 0;
  gestureLabel = gesture;
  lastSampleTime = 0;
  Serial.printf("[ESP] Bắt đầu thu %d mẫu...\n", SAMPLE_COUNT);
}

// ========================
// --- SETUP ---
// ========================
void setup() {
  Serial.begin(115200);
  Wire.begin();

  connectWiFi();

  if (!mpu.begin()) {
    Serial.println("❌ Không tìm thấy MPU6050!");
    while (1) delay(10);
  }

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  while (!connectServer()) {
    delay(3000);
  }
}

// ========================
// --- LOOP ---
// ========================
void loop() {
  // Giữ kết nối WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Mất kết nối, thử lại...");
    connectWiFi();
  }

  // Giữ kết nối TCP tới server
  if (!client.connected()) {
    Serial.println("[Server] Mất kết nối, reconnect...");
    if (!connectServer()) {
      delay(3000);
      return;
    }
  }

  // --- Gửi ping định kỳ để giữ kết nối ---
  if (millis() - lastPingTime > 10000) { // mỗi 10s gửi 1 ping
    client.println("PING");
    lastPingTime = millis();
  }

  // --- Nhận lệnh từ server ---
  if (client.available()) {
    String cmd = client.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      Serial.printf("[CMD] Nhận từ server: %s\n", cmd.c_str());
    }

    if (cmd.startsWith("start")) {
      int gesture = cmd.substring(6).toInt();
      if (!isCollecting) startCollection(gesture);
    }
  }

  // --- Gửi dữ liệu IMU ---
  if (isCollecting) {
    if (millis() - lastSampleTime >= COLLECTION_INTERVAL_MS) {
      lastSampleTime = millis();

      sensors_event_t a, g, temp;
      mpu.getEvent(&a, &g, &temp);

      String data = String(gestureLabel) + "," +
                    String(a.acceleration.x, 2) + "," +
                    String(a.acceleration.y, 2) + "," +
                    String(a.acceleration.z, 2) + "," +
                    String(g.gyro.x, 2) + "," +
                    String(g.gyro.y, 2) + "," +
                    String(g.gyro.z, 2);

      client.println(data);
      currentSample++;

      if (currentSample >= SAMPLE_COUNT) {
        client.println("DONE");
        Serial.println("[ESP] Thu xong, gửi DONE ✅");
        isCollecting = false;
      }
    }
  }

  delay(5);
}
