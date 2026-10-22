// Voice Consistent - placeholder firmware
// Target: ESP32-S3 (N16R8)
//
// This sketch only prints a startup message. Wi-Fi, I2S audio and Gemini
// integration are not implemented yet.

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("Voice Consistent: starting up (placeholder firmware)");
}

void loop() {
  delay(1000);
}
