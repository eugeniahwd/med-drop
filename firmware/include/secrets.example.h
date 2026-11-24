// Salin file ini menjadi secrets.h (di folder yang sama) lalu isi.
// secrets.h tidak ikut ke GitHub.
#pragma once

#define WIFI_SSID "nama-wifi"            // ESP32 hanya bisa Wi-Fi 2.4 GHz
#define WIFI_PASSWORD "password-wifi"
#define SERVER_URL "http://192.168.1.10:8000"  // IP laptop, tercetak saat server dijalankan
#define DEVICE_KEY "sama-dengan-DEVICE_KEY-di-.env"
#define DEVICE_ID "BIN-001"
#define DEFAULT_MEMBER "MBR-0001"
