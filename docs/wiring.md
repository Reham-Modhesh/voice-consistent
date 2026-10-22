# Wiring

> ⚠️ **Every pin assignment below is provisional and has NOT been physically tested.**
> Before powering the circuit, check the exact pinout of your ESP32-S3 board and the documentation for your specific microphone and amplifier modules. Pin labels and supported voltages differ between module vendors.

## INMP441 Microphone (I2S input)

| INMP441 pin | Connects to | Notes |
|---|---|---|
| SCK | GPIO 12 | Provisional. I2S bit clock |
| WS | GPIO 13 | Provisional. I2S word select |
| SD | GPIO 11 | Provisional. I2S serial data out |
| L/R | GND | Provisional. Selects the left channel |
| VDD | 3.3V | Provisional. Do not connect to 5V |
| GND | GND | Provisional |

## MAX98357A Amplifier (I2S output)

| MAX98357A pin | Connects to | Notes |
|---|---|---|
| BCLK | GPIO 6 | Provisional. I2S bit clock |
| LRC | GPIO 5 | Provisional. I2S word select (left/right clock) |
| DIN | GPIO 7 | Provisional. I2S serial data in |
| GND | Common GND | Provisional. Shared with the ESP32-S3 ground |
| VIN | Suitable verified supply | Provisional. See safety notes |
| Speaker + / − | Speaker terminals | Provisional. Amplifier output terminals only |

## Safety Notes

- **Do not assume the amplifier can safely draw speaker power from the ESP32-S3 3.3V pin.** A 3W speaker can draw more current than the board's 3.3V regulator can supply.
- **Check the amplifier module's supported supply voltage** in its datasheet or vendor documentation before connecting VIN.
- **Connect the speaker only across the amplifier's positive and negative speaker terminals.** Never connect either speaker wire directly to an ESP32 GPIO pin or to GND.
- Use a common ground between the ESP32-S3 and the amplifier's supply.
- Check that the chosen GPIOs are not used by flash, PSRAM, USB or strapping functions on your specific board.
- Start with a low volume when testing audio output for the first time.
- Disconnect power before changing any wiring.

## Verification Status

This wiring has not been physically built or tested. Update this document once each connection has been checked on real hardware.
