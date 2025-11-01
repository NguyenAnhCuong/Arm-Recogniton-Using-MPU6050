#include <WiFi.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// --- Cấu hình mạng ---
const char* ssid = "Onepiece";
const char* password = "12345678";

// --- Cấu hình Server ---
const char* serverIP = "10.184.254.142";// IP máy chạy Python server
const int serverPort = 6000;

// --- Cấu hình chân ---
#define LED_PIN 2
#define BUZZER_PIN 4
#define FAN_PIN 5

// --- Cấu hình LCD I2C ---
LiquidCrystal_I2C lcd(0x27, 16, 2); // Địa chỉ 0x27 hoặc 0x3F tùy module

// --- Biến kết nối ---
WiFiClient client;

// ============================================================
// --- HÀM KẾT NỐI SERVER ---
// ============================================================
void connectToServer() {
  Serial.print("🔗 Đang kết nối server ");
  Serial.print(serverIP);
  Serial.print(":");
  Serial.println(serverPort);

  if (client.connect(serverIP, serverPort)) {
    Serial.println("✅ Đã kết nối server Python!");
    client.println("ESP32_CONNECTED");
  } else {
    Serial.println("❌ Kết nối thất bại.");
  }
}

// ============================================================
// --- HÀM HIỂN THỊ VÀ ĐẾM NGƯỢC LCD ---
// ============================================================
void lcdCountdown() {
  lcd.backlight();          // 🔥 Bật LCD khi bắt đầu đếm
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("🕒 Bat dau sau:");

  for (int i = 10; i >= 0; i--) {
    lcd.setCursor(0, 1);
    lcd.print("     ");
    lcd.setCursor(5, 1);
    lcd.print(i);
    lcd.print("s   ");
    delay(1000);
  }

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("👉 San sang!");
  delay(1500);

  lcd.clear();
  lcd.noBacklight();        // 💡 Tắt màn hình LCD sau khi xong
  Serial.println("💤 LCD da tat sau dem nguoc");
}

// ============================================================
// --- SETUP ---
// ============================================================
void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(FAN_PIN, OUTPUT);

  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(FAN_PIN, LOW);

  // --- Khởi động LCD ---
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("ESP32 dang ket noi");
  delay(500);

  // --- Kết nối WiFi ---
  Serial.println("🔌 Ket noi WiFi...");
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n✅ Da ket noi WiFi!");
  Serial.print("📶 IP ESP32: ");
  Serial.println(WiFi.localIP());

  lcd.clear();
  lcd.print("WiFi OK");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP());
  delay(1000);

  lcd.noBacklight();   // 💡 Tắt LCD sau khi khởi động xong

  connectToServer();
}

// ============================================================
// --- LOOP ---
// ============================================================
void loop() {
  if (!client.connected()) {
    Serial.println("⚠️ Mat ket noi server, dang thu lai...");
    connectToServer();
    delay(2000);
    return;
  }

  if (client.available()) {
    String cmd = client.readStringUntil('\n');
    cmd.trim();

    Serial.print("📩 Lenh nhan: ");
    Serial.println(cmd);

    if (cmd == "LED_ON") {
      digitalWrite(LED_PIN, HIGH);
      Serial.println("💡 LED bat");
      client.println("OK_LED_ON");

    } else if (cmd == "LED_OFF") {
      digitalWrite(LED_PIN, LOW);
      Serial.println("💤 LED tat");
      client.println("OK_LED_OFF");

    } else if (cmd == "BUZZER_ON") {
      digitalWrite(BUZZER_PIN, HIGH);
      Serial.println("🔊 Coi bat");
      client.println("OK_BUZZER_ON");

    } else if (cmd == "BUZZER_OFF") {
      digitalWrite(BUZZER_PIN, LOW);
      Serial.println("🔇 Coi tat");
      client.println("OK_BUZZER_OFF");

    } else if (cmd == "FAN_ON") {
      digitalWrite(FAN_PIN, HIGH);
      Serial.println("🌀 Quat bat");
      client.println("OK_FAN_ON");

    } else if (cmd == "FAN_OFF") {
      digitalWrite(FAN_PIN, LOW);
      Serial.println("🧊 Quat tat");
      client.println("OK_FAN_OFF");

    } else if (cmd == "LCD_COUNTDOWN") {
      Serial.println("🕒 LCD dem nguoc 10s");
      lcdCountdown();
      client.println("OK_LCD_DONE");

    } else {
      Serial.println("❓ Lenh khong hop le");
    }
  }

  delay(50);
}
