#include <WiFi.h>
#include <WebSocketsClient.h>   // "WebSockets" library by Markus Sattler (links2004), 2.7.x
#include <driver/i2s.h>         // legacy I2S driver
#include <freertos/stream_buffer.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ============================================================
//  ESP32 + INMP441 + MAX98357A + I2C OLED + Gemini Live
// ============================================================

#define FW_VERSION "live-0.2"

// ---- OLED Display Config ----
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define SCREEN_ADDRESS 0x3C  // العنوان الافتراضي للشاشة
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ---- Wi-Fi Details ----
const char* WIFI_SSID     = "Saeed707";
const char* WIFI_PASSWORD = "12341234";

// ---- FastAPI Server Address ----
const char* SERVER_HOST   = "172.20.10.2";
const uint16_t SERVER_PORT = 8000;
const char* SERVER_PATH   = "/ws";

#define ALLOW_BARGE_IN 0

// ---- INMP441 pins (Microphone) ----
#define MIC_I2S_PORT I2S_NUM_0
#define MIC_WS_PIN   25
#define MIC_SD_PIN   32
#define MIC_SCK_PIN  33

// ---- MAX98357A pins (Speaker) ----
#define SPEAKER_I2S_PORT I2S_NUM_1
#define SPK_WS_PIN       26  
#define SPK_BCLK_PIN     27  
#define SPK_DIN_PIN      14  

// ---- Audio settings ----
static const uint32_t MIC_SAMPLE_RATE = 16000;
static const uint32_t SPK_SAMPLE_RATE = 24000;
static const int I2S_BUFFER_LEN = 512;
static const size_t MIC_FRAME_BYTES = 1280;          
static const size_t MIC_BUFFER_BYTES = 8192;         
static const size_t SPK_BUFFER_BYTES = 32768;        
static const size_t SPK_PREBUFFER_BYTES = 7200;      
static const uint32_t MIC_MUTE_HOLD_MS = 300;

// ---- Connection settings ----
static const uint32_t WIFI_RETRY_MS = 10000;
static const uint32_t WS_RECONNECT_MS = 3000;

WebSocketsClient webSocket;
StreamBufferHandle_t micStream = nullptr;   
StreamBufferHandle_t spkStream = nullptr;   

volatile bool serverReady = false;          
volatile uint8_t playEpoch = 0;             
volatile bool flushPlayback = false;        
volatile bool turnEnded = false;            
volatile bool speakerActive = false;
volatile uint32_t lastSpeakerAudioMs = 0;
volatile uint32_t spkOverflowBytes = 0;
volatile uint32_t micDroppedBytes = 0;

enum SystemState { STATE_INIT, STATE_CONNECTING, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_SPEAKING };
volatile SystemState currentState = STATE_INIT;

// ---- Display Functions ----
void drawFace(SystemState state) {
  display.clearDisplay();
  
  switch(state) {
    case STATE_INIT:
    case STATE_CONNECTING:
      display.setTextSize(1);
      display.setTextColor(SSD1306_WHITE);
      display.setCursor(15, 25);
      display.println("Connecting...");
      break;

    case STATE_IDLE:
      // عينان عاديتان للانتظار
      display.fillCircle(40, 25, 10, SSD1306_WHITE);
      display.fillCircle(88, 25, 10, SSD1306_WHITE);
      display.drawLine(50, 48, 78, 48, SSD1306_WHITE);
      break;

    case STATE_LISTENING:
      // عينان مفتوحتان للاستماع
      display.fillCircle(40, 22, 12, SSD1306_WHITE);
      display.fillCircle(88, 22, 12, SSD1306_WHITE);
      display.drawCircle(64, 48, 6, SSD1306_WHITE);
      break;

    case STATE_THINKING:
      // عينان تتطلعان للأعلى
      display.fillCircle(40, 18, 9, SSD1306_WHITE);
      display.fillCircle(88, 18, 9, SSD1306_WHITE);
      display.drawLine(55, 48, 73, 48, SSD1306_WHITE);
      break;

    case STATE_SPEAKING: {
      // عينان سعيدتان وفم يتحرك مع الكلام
      display.fillTriangle(30, 28, 40, 18, 50, 28, SSD1306_WHITE);
      display.fillTriangle(78, 28, 88, 18, 98, 28, SSD1306_WHITE);
      static bool mouthOpen = false;
      mouthOpen = !mouthOpen;
      if (mouthOpen) {
        display.fillRoundRect(50, 42, 28, 12, 4, SSD1306_WHITE);
      } else {
        display.fillRoundRect(52, 45, 24, 5, 2, SSD1306_WHITE);
      }
      break;
    }
  }
  display.display();
}

bool initMicrophone() {
  i2s_config_t micConfig = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = (int)MIC_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = (i2s_comm_format_t)I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = I2S_BUFFER_LEN,
    .use_apll = false
  };

  i2s_pin_config_t micPins = {
    .mck_io_num = I2S_PIN_NO_CHANGE,
    .bck_io_num = MIC_SCK_PIN,
    .ws_io_num = MIC_WS_PIN,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = MIC_SD_PIN
  };

  esp_err_t err = i2s_driver_install(MIC_I2S_PORT, &micConfig, 0, NULL);
  if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) return false;

  err = i2s_set_pin(MIC_I2S_PORT, &micPins);
  if (err != ESP_OK) return false;
  i2s_zero_dma_buffer(MIC_I2S_PORT);
  return true;
}

bool initSpeaker() {
  i2s_config_t speakerConfig = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = (int)SPK_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = (i2s_comm_format_t)I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false,
    .tx_desc_auto_clear = true
  };

  i2s_pin_config_t speakerPins = {
    .mck_io_num = I2S_PIN_NO_CHANGE,
    .bck_io_num = SPK_BCLK_PIN,
    .ws_io_num = SPK_WS_PIN,
    .data_out_num = SPK_DIN_PIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  esp_err_t err = i2s_driver_install(SPEAKER_I2S_PORT, &speakerConfig, 0, NULL);
  if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) return false;

  err = i2s_set_pin(SPEAKER_I2S_PORT, &speakerPins);
  if (err != ESP_OK) return false;
  i2s_zero_dma_buffer(SPEAKER_I2S_PORT);
  return true;
}

void micTask(void* arg) {
  static int32_t rawSamples[256];
  static int16_t pcm[256];
  for (;;) {
    size_t bytesRead = 0;
    esp_err_t err = i2s_read(MIC_I2S_PORT, rawSamples, sizeof(rawSamples), &bytesRead, portMAX_DELAY);
    if (err != ESP_OK || bytesRead == 0) continue;

    size_t count = bytesRead / sizeof(int32_t);
    for (size_t i = 0; i < count; i++) {
      pcm[i] = (int16_t)(rawSamples[i] >> 15); // معالجة الصوت والـ Gain
    }
    size_t bytes = count * sizeof(int16_t);
    size_t queued = xStreamBufferSend(micStream, pcm, bytes, 0);
    if (queued < bytes) micDroppedBytes += bytes - queued;
  }
}

void playbackTask(void* arg) {
  static uint8_t buffer[1024];
  bool playing = false;
  for (;;) {
    if (flushPlayback) {
      while (xStreamBufferReceive(spkStream, buffer, sizeof(buffer), 0) > 0) {}
      i2s_zero_dma_buffer(SPEAKER_I2S_PORT);
      playing = false;
      speakerActive = false;
      turnEnded = false;
      flushPlayback = false;
    }

    if (!playing) {
      size_t available = xStreamBufferBytesAvailable(spkStream);
      if (available >= SPK_PREBUFFER_BYTES || (turnEnded && available > 0)) {
        playing = true;
        speakerActive = true;
      } else {
        vTaskDelay(pdMS_TO_TICKS(5));
        continue;
      }
    }

    size_t got = xStreamBufferReceive(spkStream, buffer, sizeof(buffer), pdMS_TO_TICKS(20));
    if (got == 0) {
      playing = false;
      speakerActive = false;
      turnEnded = false;
      continue;
    }

    size_t written = 0;
    i2s_write(SPEAKER_I2S_PORT, buffer, got, &written, portMAX_DELAY);
    lastSpeakerAudioMs = millis();
  }
}

bool micMuted() {
#if ALLOW_BARGE_IN
  return false;
#else
  return speakerActive ||
         xStreamBufferBytesAvailable(spkStream) > 0 ||
         millis() - lastSpeakerAudioMs < MIC_MUTE_HOLD_MS;
#endif
}

bool jsonField(const char* json, const char* key, char* out, size_t outSize) {
  char pattern[24];
  snprintf(pattern, sizeof(pattern), "\"%s\"", key);
  const char* p = strstr(json, pattern);
  if (!p) return false;
  p += strlen(pattern);
  while (*p == ' ' || *p == ':') p++;
  bool quoted = (*p == '"');
  if (quoted) p++;
  size_t n = 0;
  while (*p && n + 1 < outSize && (quoted ? *p != '"' : (*p != ',' && *p != '}' && *p != ' '))) {
    out[n++] = *p++;
  }
  out[n] = '\0';
  return true;
}

void handleControlMessage(const char* json) {
  char type[24];
  if (!jsonField(json, "type", type, sizeof(type))) return;

  if (strcmp(type, "ready") == 0) {
    serverReady = true;
    currentState = STATE_IDLE;
    Serial.println("Gemini session ready. Start talking.");
  } else if (strcmp(type, "reconnecting") == 0) {
    serverReady = false;
    currentState = STATE_CONNECTING;
  } else if (strcmp(type, "interrupted") == 0) {
    char epoch[8];
    if (jsonField(json, "epoch", epoch, sizeof(epoch))) playEpoch = (uint8_t)atoi(epoch);
    flushPlayback = true;
  } else if (strcmp(type, "turn_complete") == 0) {
    turnEnded = true;
  }
}

void onWebSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED: {
      String hello = String("{\"type\":\"hello\",\"fw\":\"") + FW_VERSION + "\"}";
      webSocket.sendTXT(hello);
      break;
    }
    case WStype_DISCONNECTED:
      serverReady = false;
      flushPlayback = true;
      currentState = STATE_CONNECTING;
      break;
    case WStype_TEXT:
      handleControlMessage((const char*)payload);
      break;
    case WStype_BIN: {
      if (length < 3 || payload[0] != playEpoch) break;
      size_t pcmBytes = (length - 1) & ~(size_t)1;
      size_t queued = xStreamBufferSend(spkStream, payload + 1, pcmBytes, 0);
      if (queued < pcmBytes) spkOverflowBytes += pcmBytes - queued;
      break;
    }
    default:
      break;
  }
}

void maintainWiFi() {
  static uint32_t lastAttempt = 0;
  bool connected = (WiFi.status() == WL_CONNECTED);

  if (!connected && millis() - lastAttempt > WIFI_RETRY_MS) {
    lastAttempt = millis();
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

void pumpMicrophone() {
  static uint8_t frame[MIC_FRAME_BYTES];
  while (xStreamBufferBytesAvailable(micStream) >= MIC_FRAME_BYTES) {
    xStreamBufferReceive(micStream, frame, MIC_FRAME_BYTES, 0);
    if (serverReady && !micMuted()) {
      webSocket.sendBIN(frame, MIC_FRAME_BYTES);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  // تهيئة الشاشة على المنافذ البديلة (SDA = GPIO 18, SCL = GPIO 19)
  Wire.begin(18, 19); 
  if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
  } else {
    display.clearDisplay();
    drawFace(STATE_CONNECTING);
  }

  micStream = xStreamBufferCreate(MIC_BUFFER_BYTES, 1);
  spkStream = xStreamBufferCreate(SPK_BUFFER_BYTES, 1);

  initMicrophone();
  initSpeaker();

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  webSocket.begin(SERVER_HOST, SERVER_PORT, SERVER_PATH, "");
  webSocket.onEvent(onWebSocketEvent);
  webSocket.setReconnectInterval(WS_RECONNECT_MS);

  xTaskCreatePinnedToCore(micTask, "mic", 4096, nullptr, 5, nullptr, 1);
  xTaskCreatePinnedToCore(playbackTask, "playback", 4096, nullptr, 6, nullptr, 1);
}

void loop() {
  maintainWiFi();
  webSocket.loop();
  pumpMicrophone();

  // تحديث حالة الوجه والتفاعل مع حركة الصوت
  if (serverReady) {
    if (speakerActive) {
      currentState = STATE_SPEAKING;
    } else if (!micMuted()) {
      currentState = STATE_LISTENING;
    } else {
      currentState = STATE_IDLE;
    }
  } else {
    currentState = STATE_CONNECTING;
  }

  static uint32_t lastDisplayUpdate = 0;
  if (millis() - lastDisplayUpdate > 100) { 
    lastDisplayUpdate = millis();
    drawFace(currentState);
  }

  delay(1);
}