# Amiccon_A7137_ProtocolAnalyzerHLA

A custom **Saleae High Level Analyzer (HLA)** for the **Amiccom A7137 protocol** decoding.

## Overview

This HLA assumes that the SPI analyzer is configured in **4-bit mode**.  

Key features:
- Detects **strobes 0x8–0xF** (Sleep, Idle, Standby, PLL, RX, TX, FIFO pointer resets) of 4 and 8 bit depth.
- Detects **R/W registers command 0x00–0x3F**.
- Guarantees **monotonic timestamps** to avoid ordering errors in Saleae Logic.

## Installation

1. Open **Logic 2 → Extensions**.
2. **Load Extension** 
3. Select the `extension.json` file.
4. Add a standard **SPI analyzer** to your capture. SPI analyzer must be configured in **4-bit mode**
5. Add **StrobeFromSpiHla** as a High Level Analyzer on top of SPI.
6. Configure the settings (Source, Require CS, Debug).

---

