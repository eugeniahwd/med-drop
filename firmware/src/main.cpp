// Firmware MedDrop untuk ESP32 Dev Module.
//
// Board ini belum disambung ke sensor dan aktuator, jadi:
//   - foto diambil dari memori (include/photos.h) sebagai pengganti kamera
//   - berat dan barcode diketik di Serial Monitor sebagai pengganti load cell dan pemindai barcode
//   - pintu, kunci, dan trap door hanya dicetak ke Serial Monitor; LED bawaan (GPIO2) jadi lampu status
// Alurnya tetap sungguhan: ESP32 mengirim data lewat Wi-Fi ke server di laptop, server memutuskan,
// lalu ESP32 bertindak sesuai keputusan. Server juga menyimpan salinannya ke Supabase.

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>

#include "photos.h"
#include "secrets.h"

const int STATUS_LED_PIN = 2;   // LED bawaan di banyak board ESP32; aman walau tidak ada
const int BUTTON_PIN = 0;  // tombol BOOT, dipakai sebagai tombol "setor cepat"
const unsigned long HEARTBEAT_MS = 10000;
const char *FIRMWARE_VERSION = "0.1.0";
const char *BOUNDARY = "----meddrop-esp32";

struct Preset {
  int photo;
  const char *barcode;
  float weight;
  const char *label;
};

// Skenario siap pakai: ketik 1 sampai 4 di Serial Monitor.
const Preset PRESETS[] = {
    {0, "2000000000015", 20.0, "Entrostop, matching barcode, 20 g (should be accepted)"},
    {0, "2000000000015", 8.0, "Entrostop, empty package 8 g (should be rejected)"},
    {1, "2000000000015", 20.0, "Promag photo with an Entrostop barcode (mismatch)"},
    {2, "2000000000015", 25.0, "Plastic bottle with an Entrostop barcode (not a medicine)"},
};
const int PRESET_COUNT = sizeof(PRESETS) / sizeof(PRESETS[0]);

String memberToken = DEFAULT_MEMBER;
String inputLine;
unsigned long lastHeartbeat = 0;
bool serverOnline = false;

void blink(int times, int ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(ms);
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(ms);
  }
}

void printHelp() {
  Serial.println();
  Serial.println("MedDrop ESP32. Commands:");
  for (int i = 0; i < PRESET_COUNT; i++) {
    Serial.printf("  %d                 %s\n", i + 1, PRESETS[i].label);
  }
  Serial.println("  send P B W        custom: photo number P, barcode B (or -), weight W grams");
  Serial.println("  member MBR-0002   change the member number");
  Serial.println("  help              show this list");
  Serial.println("Photos stored in this board:");
  for (int i = 0; i < PHOTO_COUNT; i++) {
    Serial.printf("  %d = %s (%u bytes)\n", i + 1, PHOTOS[i].name, (unsigned)PHOTOS[i].size);
  }
  Serial.println("Pressing the BOOT button sends scenario 1.");
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Connecting to Wi-Fi %s", WIFI_SSID);
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWi-Fi connected, IP %s, signal %d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else {
    Serial.println("\nWi-Fi not connected yet, the board will keep retrying.");
  }
}

// Kabari server bahwa mesin masih hidup. Server menyimpannya ke tabel devices di Supabase.
void sendHeartbeat() {
  bool ok = false;
  if (WiFi.status() == WL_CONNECTED) {
    JsonDocument doc;
    doc["device_id"] = DEVICE_ID;
    doc["rssi"] = WiFi.RSSI();
    doc["uptime_s"] = millis() / 1000;
    doc["firmware"] = FIRMWARE_VERSION;
    doc["ip"] = WiFi.localIP().toString();
    String body;
    serializeJson(doc, body);

    HTTPClient http;
    http.begin(String(SERVER_URL) + "/api/device/heartbeat");
    http.setTimeout(5000);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-Key", DEVICE_KEY);
    ok = http.POST(body) == 200;
    http.end();
  } else {
    WiFi.reconnect();
  }
  if (ok != serverOnline) {  // cetak hanya saat status berubah supaya log tidak penuh
    Serial.println(ok ? "[heartbeat] Server reachable, machine is online" : "[heartbeat] Server NOT reachable");
    serverOnline = ok;
  }
}

// Mode aman: kalau tidak ada keputusan dari server, barang dikembalikan lewat pintu depan.
void safeMode(const String &reason) {
  Serial.printf("[SAFE MODE] %s\n", reason.c_str());
  Serial.println("[door] Front door unlocked and reopened, please take your item back");
  blink(6, 80);
}

void deposit(int photo, const String &barcode, float weight) {
  if (photo < 0 || photo >= PHOTO_COUNT) {
    Serial.println("Unknown photo number.");
    return;
  }
  Serial.println("\n=== New drop-off ===");
  Serial.printf("Member %s | photo %s | barcode %s | weight %.1f g\n", memberToken.c_str(), PHOTOS[photo].name,
                barcode.length() ? barcode.c_str() : "-", weight);
  Serial.println("[door] Front door open, item placed on the scale");
  Serial.println("[door] Front door closed and locked");
  Serial.println("[check] Sending photo, barcode, and weight to the server...");
  digitalWrite(STATUS_LED_PIN, HIGH);

  if (WiFi.status() != WL_CONNECTED) {
    digitalWrite(STATUS_LED_PIN, LOW);
    safeMode("Wi-Fi is not connected");
    return;
  }

  // Susun body multipart/form-data: isian teks lalu file foto.
  String head;
  auto field = [&head](const char *name, const String &value) {
    head += String("--") + BOUNDARY + "\r\nContent-Disposition: form-data; name=\"" + name + "\"\r\n\r\n" + value + "\r\n";
  };
  field("member_token", memberToken);
  field("bin_id", DEVICE_ID);
  field("weight_g", String(weight, 2));
  if (barcode.length()) field("barcode_text", barcode);
  head += String("--") + BOUNDARY + "\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"photo.jpg\"\r\n"
          "Content-Type: image/jpeg\r\n\r\n";
  String tail = String("\r\n--") + BOUNDARY + "--\r\n";

  size_t total = head.length() + PHOTOS[photo].size + tail.length();
  uint8_t *body = (uint8_t *)malloc(total);
  if (!body) {
    digitalWrite(STATUS_LED_PIN, LOW);
    safeMode("Not enough memory to build the request");
    return;
  }
  memcpy(body, head.c_str(), head.length());
  memcpy(body + head.length(), PHOTOS[photo].data, PHOTOS[photo].size);
  memcpy(body + head.length() + PHOTOS[photo].size, tail.c_str(), tail.length());

  HTTPClient http;
  http.begin(String(SERVER_URL) + "/api/device/verify");
  http.setTimeout(15000);
  http.addHeader("Content-Type", String("multipart/form-data; boundary=") + BOUNDARY);
  http.addHeader("X-Device-Key", DEVICE_KEY);
  int code = http.POST(body, total);
  free(body);
  String response = code > 0 ? http.getString() : "";
  http.end();
  digitalWrite(STATUS_LED_PIN, LOW);

  if (code <= 0) {
    safeMode(String("Server not reachable (") + HTTPClient::errorToString(code) + ")");
    return;
  }
  JsonDocument doc;
  if (deserializeJson(doc, response) || code != 200) {
    const char *detail = doc["detail"] | "unexpected answer";
    safeMode(String("Server answered ") + code + ": " + detail);
    return;
  }

  const char *decision = doc["decision"] | "REJECT";
  Serial.printf("[result] %s, %s. %s\n", decision, (const char *)(doc["reason_code"] | ""),
                (const char *)(doc["reason_text"] | ""));
  Serial.printf("[result] Photo recognized as %s (%.0f%%)\n", (const char *)(doc["product"] | "-"),
                (float)(doc["confidence"] | 0.0) * 100);
  if (strcmp(decision, "ACCEPT") == 0) {
    Serial.printf("[trap door] Tilting back, item drops into the bin. +%d points (total %d)\n",
                  (int)(doc["points_awarded"] | 0), (int)(doc["points_total"] | 0));
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(2000);
    digitalWrite(STATUS_LED_PIN, LOW);
  } else {
    Serial.println("[trap door] Tilting forward, return door open: please take your item back");
    blink(3, 300);
  }
}

void handleCommand(String line) {
  line.trim();
  if (line.isEmpty()) return;
  if (line == "help") {
    printHelp();
  } else if (line.startsWith("member ")) {
    memberToken = line.substring(7);
    memberToken.trim();
    Serial.printf("Member set to %s\n", memberToken.c_str());
  } else if (line.startsWith("send ")) {
    char barcode[32];
    int photo;
    float weight;
    if (sscanf(line.c_str() + 5, "%d %31s %f", &photo, barcode, &weight) == 3) {
      deposit(photo - 1, strcmp(barcode, "-") == 0 ? String("") : String(barcode), weight);
    } else {
      Serial.println("Format: send <photo 1-3> <barcode or -> <weight>");
    }
  } else if (line.toInt() >= 1 && line.toInt() <= PRESET_COUNT) {
    const Preset &p = PRESETS[line.toInt() - 1];
    Serial.printf("Scenario %ld: %s\n", line.toInt(), p.label);
    deposit(p.photo, p.barcode, p.weight);
  } else {
    Serial.println("Unknown command, type help.");
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  delay(500);
  connectWiFi();
  sendHeartbeat();
  lastHeartbeat = millis();
  printHelp();
}

void loop() {
  if (millis() - lastHeartbeat >= HEARTBEAT_MS) {
    sendHeartbeat();
    lastHeartbeat = millis();
  }
  if (digitalRead(BUTTON_PIN) == LOW) {
    delay(50);  // tunggu pantulan tombol reda
    if (digitalRead(BUTTON_PIN) == LOW) {
      handleCommand("1");
      while (digitalRead(BUTTON_PIN) == LOW) delay(10);
    }
  }
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      handleCommand(inputLine);
      inputLine = "";
    } else {
      inputLine += c;
    }
  }
}
