# Wiring

> ⚠️ **These pin assignments match the current firmware for a classic ESP32 Dev Module. Treat them as provisional until each connection has been checked on your hardware.**
> Before powering the circuit, check the exact pinout of your ESP32 board and the documentation for your specific microphone and amplifier modules. Pin labels and supported voltages differ between module vendors.

The GPIO numbers are defined at the top of `firmware/VoiceConsistent/VoiceConsistent.ino`. If you change the wiring, change them there too.

## INMP441 Microphone (I2S input, port 0)

| INMP441 pin | Connects to | Notes |
|---|---|---|
| SCK | GPIO 33 | Provisional. I2S bit clock (`MIC_SCK_PIN`) |
| WS | GPIO 25 | Provisional. I2S word select (`MIC_WS_PIN`) |
| SD | GPIO 32 | Provisional. I2S serial data out (`MIC_SD_PIN`) |
| L/R | GND | Provisional. Selects the left channel, which the firmware reads |
| VDD | 3.3V | Provisional. Do not connect to 5V |
| GND | GND | Provisional |

## MAX98357A Amplifier (I2S output, port 1)

| MAX98357A pin | Connects to | Notes |
|---|---|---|
| BCLK | GPIO 27 | Provisional. I2S bit clock (`SPK_BCLK_PIN`) |
| LRC | GPIO 26 | Provisional. I2S word select / left-right clock (`SPK_WS_PIN`) |
| DIN | GPIO 14 | Provisional. I2S serial data in (`SPK_DIN_PIN`) |
| GND | Common GND | Provisional. Shared with the ESP32 ground |
| VIN | Suitable verified supply | Provisional. See safety notes |
| Speaker + / − | Speaker terminals | Provisional. Amplifier output terminals only |

## Safety Notes

- **Do not assume the amplifier can safely draw speaker power from the ESP32 3.3V pin.** A 3W speaker can draw more current than the board's 3.3V regulator can supply.
- **Check the amplifier module's supported supply voltage** in its datasheet or vendor documentation before connecting VIN.
- **Connect the speaker only across the amplifier's positive and negative speaker terminals.** Never connect either speaker wire directly to an ESP32 GPIO pin or to GND.
- Use a common ground between the ESP32 and the amplifier's supply.
- GPIO 14 and GPIO 27 output signals briefly at boot on some ESP32 boards. Check your board's documentation if the amplifier makes noise at startup.
- Start with a low volume when testing audio output for the first time.
- Disconnect power before changing any wiring.

## I2S Ports

The microphone and amplifier use separate I2S peripherals: the INMP441 on I2S port 0 (receive, 16 kHz) and the MAX98357A on I2S port 1 (transmit, 24 kHz). The classic ESP32 has two I2S peripherals, so both run at the same time, which the real-time conversation needs. They do not share clock pins.

## Verification Status

The firmware notes that the microphone pins come from an earlier working microphone test. The Gemini Live migration did not change any pins. The speaker wiring and the full circuit have not been verified in this repository. Update this document once each connection has been checked on real hardware.
