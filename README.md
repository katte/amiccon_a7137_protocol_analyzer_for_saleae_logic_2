# Amiccon_A7137_ProtocolAnalyzerHLA

A custom **Saleae High Level Analyzer (HLA)** for the **Amiccom A7137 protocol** strobe decoding.

## Overview

This HLA assumes that the SPI analyzer is configured in **4-bit mode**.  
It will emit a **strobe frame** only if **exactly one 4-bit word** is transferred between **CS enable** and **CS disable**.  

This prevents false strobe detections inside normal 8-bit data streams.

Key features:
- Detects **strobes 0x8–0xF** (Sleep, Idle, Standby, PLL, RX, TX, FIFO pointer resets).
- Works on **MOSI**, **MISO**, or **Both** (configurable).
- Optional **debug frames** show all 4-bit words seen within CS windows.
- Guarantees **monotonic timestamps** to avoid ordering errors in Saleae Logic.

## Strobe Map

| Value | Name                          |
|-------|-------------------------------|
| 0x8   | Strobe: SleepMode             |
| 0x9   | Strobe: Idle Mode             |
| 0xA   | Strobe: Standby Mode          |
| 0xB   | Strobe: PLL Mode              |
| 0xC   | Strobe: RX Mode               |
| 0xD   | Strobe: TX Mode               |
| 0xE   | Strobe: Fifo Write Ptr Reset  |
| 0xF   | Strobe: Fifo Read Ptr Reset   |

## Settings

- **Source**  
  Select which SPI stream to decode: `MOSI`, `MISO`, or `Both`.

- **Require CS Active**  
  `True` → Only decode inside chip select windows.  
  `False` → Decode all SPI results.

- **Emit Debug Frames**  
  `True` → Emit debug frames showing each 4-bit word seen with count.  
  `False` → Only emit strobe frames.

## Installation

1. Open **Logic 2 → Extensions**.
2. **Load Extension** 
3. Select the `extension.json` file.
4. Add a standard **SPI analyzer** to your capture.
5. Add **StrobeFromSpiHla** as a High Level Analyzer on top of SPI.
6. Configure the settings (Source, Require CS, Debug).

## Notes

- This HLA **does not emit CS frames** (`enable/disable`) to avoid ordering issues in Saleae Logic.
- Only windows with **exactly one data word** are considered valid strobes.
- If more than one word is seen during CS active, no strobe is emitted.

---

