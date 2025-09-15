# HighLevelAnalyzer.py (CS-single-word, 4-bit assumed, monotonic emission)
# - SPI always 4-bit (assumed).
# - Ensures that the begin time of emitted frames is strictly increasing.

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, ChoicesSetting

_STROBE_MAP = {
    0x8: 'SleepMode',
    0x9: 'Idle Mode',
    0xA: 'Standby Mode',
    0xB: 'PLL Mode',
    0xC: 'RX Mode',
    0xD: 'TX Mode',
    0xE: 'Fifo Write Pointer Reset',
    0xF: 'Fifo Read Pointer Reset',
}

_REGISTER_MAP = {
    0x00: ('Reset', 'Control Register'),
    0x01: 'Mode Control Register',
    0x02: 'Calibration Control Register',
    0x03: 'FIFO Register I',
    0x04: 'FIFO Register II',
    0x05: 'FIFO DATA Register',
    0x06: 'ID DATA Register',
    0x07: 'RC OSC Register I',
    0x08: 'RC OSC Register II',
    0x09: 'RC OSC Register III',
    0x0A: 'CKO Pin Control Register',
    0x0B: 'GIO1 Pin Control Register I',
    0x0C: 'GIO2 Pin Control Register II',
    0x0D: 'Clock Register',
    0x0E: 'PLL Register I',
    0x0F: 'PLL Register II',
    0x10: 'PLL Register III',
    0x11: 'PLL Register IV',
    0x12: 'PLL Register V',
    0x13: 'Channel Group Register I',
    0x14: 'Channel Group Register II',
    0x15: 'TX Register I',
    0x16: 'TX Register II',
    0x17: 'Delay Register I',
    0x18: 'Delay Register II',
    0x19: 'RX Register',
    0x1A: 'RX Gain Register I',
    0x1B: 'RX Gain Register II',
    0x1C: 'RX Gain Register III',
    0x1D: 'RX Gain Register IV',
    0x1E: 'RSSI Threshold Register',
    0x1F: 'ADC Control Register',
    0x20: 'Code Register I',
    0x21: 'Code Register II',
    0x22: 'Code Register III',
    0x23: 'IF Calibration Register I',
    0x24: 'IF Calibration Register II',
    0x25: 'VCO current Calibration Register',
    0x26: 'VCO band Calibration Register I',
    0x27: 'VCO band Calibration Register II',
    0x28: 'VCO Deviation Calibration Register I',
    0x29: 'VCO Deviation Calibration Register II',
    0x2A: 'DASP0',
    0x2B: 'VCO Modulation Delay Register',
    0x2C: 'Battery detect Register',
    0x2D: 'TX test Register',
    0x2E: 'Rx DEM test Register I',
    0x2F: 'Rx DEM test Register II',
    0x30: 'Charge Pump Current Register I',
    0x31: 'Charge Pump Current Register II',
    0x32: 'Crystal test Register',
    0x33: 'PLL test Register',
    0x34: 'VCO test Register I',
    0x35: 'RF Analog Test Register',
    0x36: 'AES Key data Register',
    0x37: 'Channel Select Register',
    0x38: 'ROMP0',
    0x39: 'Data Rate Clock Register',
    0x3A: 'FCR Register',
    0x3B: 'ARD Register',
    0x3C: 'AFEP Register',
    0x3D: 'FCB Register',
    0x3E: 'KEYC Register',
    0x3F: 'USID Register'
}

def _as_bool(choice: str) -> bool:
    return str(choice).lower() in ('true','yes','on','1')

class Amiccon_A7137_ProtocolAnalyzerHLA(HighLevelAnalyzer):
    result_types = {
        'strobe': {'format': '{{data.dir}}: {{data.name}} (val={{data.val}})'},
        'debug':  {'format': '{{data.dir}} {{data.msg}}'}
    }

    def __init__(self):
        self.cs_asserted = False
        self._cs_total_words = 0
        self._4bit_strobe_candidate = None
        self._8bit_strobe_candidate = None
        self._8bit_register_candidate = None
        self._first_result_start = None
        self._last_result_end = None
        self._last_emitted_begin = None  # to maintain monotonicity

    def _reset_cs(self):
        self._cs_total_words = 0
        self._4bit_strobe_candidate = None
        self._8bit_strobe_candidate = None
        self._8bit_register_candidate = None
        self._first_result_start = None
        self._last_result_end = None

    def _monotonic_times(self, start_t, end_t, fallback_span):
        """Ensure start_t > last_begin and start_t < end_t."""
        lb = self._last_emitted_begin
        # Use a small delta based on fallback_span to advance the time
        try:
            delta = fallback_span / 16
        except Exception:
            delta = None
        if lb is not None and start_t <= lb and delta is not None:
            start_t = lb + delta
            if start_t >= end_t:
                # if we overshoot, shift both beyond lb
                end_t = start_t + (delta if delta is not None else end_t - start_t)
        # Update last begin
        self._last_emitted_begin = start_t
        return start_t, end_t

    def decode(self, frame: AnalyzerFrame):
        require_cs = True

        if frame.type == 'enable':
            self.cs_asserted = True
            self._reset_cs()
            return None  # no 'cs' frame

        if frame.type == 'disable':
            # Emit conditionally as strobe only (no 'cs')
            if self._cs_total_words >= 1 and self._4bit_strobe_candidate is not None:
                # Prefer to use the real data interval
                if self._first_result_start is not None and self._last_result_end is not None:
                    start_t = self._first_result_start
                    end_t = self._last_result_end
                    if end_t <= start_t:
                        span = frame.end_time - frame.start_time
                        try:
                            start_t = frame.start_time + (span / 4)
                            end_t   = frame.start_time + (span / 2)
                        except Exception:
                            start_t, end_t = frame.start_time, frame.end_time
                else:
                    # fallback: inside the disable window
                    span = frame.end_time - frame.start_time
                    try:
                        start_t = frame.start_time + (span / 4)
                        end_t   = frame.start_time + (span / 2)
                    except Exception:
                        start_t, end_t = frame.start_time, frame.end_time

                # Enforce monotonicity
                span = frame.end_time - frame.start_time
                start_t, end_t = self._monotonic_times(start_t, end_t, span)

                if self._cs_total_words == 1 and self._4bit_strobe_candidate is not None:
                    _, nib  = self._4bit_strobe_candidate
                    name = _STROBE_MAP.get(nib)
                    direction = 'S'
                    if name is not None:
                        out = AnalyzerFrame('strobe', start_t, end_t, {
                            'dir': direction,
                            'name': name,
                            'val': f'0x{nib:X}',
                        })
                    else:
                        out = None
                else:
                    out = None
                    if self._8bit_strobe_candidate is not None:
                        _, nib, _  = self._8bit_strobe_candidate
                        name = _STROBE_MAP.get(nib)
                        direction = 'S'
                        if name is not None:
                            out = AnalyzerFrame('strobe', start_t, end_t, {
                                'dir': direction,
                                'name': name,
                                'val': f'0x{nib:X}',
                            })
                    if self._8bit_register_candidate is not None:
                        _, nib1, nib2  = self._8bit_register_candidate
                        data = ((nib1 << 4) | nib2)
                        name = _REGISTER_MAP.get(data & 0xBF)
                        if name is not None:
                            if data & 0x40:
                                direction = 'RD'
                            else:
                                direction = 'WR'
                            if isinstance(name, tuple):
                                if data & 0x40:
                                    name = name[1]
                                else:
                                    name = name[0]
                        if name is not None:
                            out = AnalyzerFrame('strobe', start_t, end_t, {
                                'dir': direction,
                                'name': name,
                                'val': f'0x{data:X}',
                            })
            else:
                out = None

            self.cs_asserted = False
            self._reset_cs()
            return out

        if frame.type != 'result':
            return None

        if require_cs and not self.cs_asserted:
            return None

        # Streams
        streams = []
        streams.append(('', frame.data['mosi']))

        if not streams:
            return None

        outputs = []

        for direction, buf in streams:
            vals = list(buf) if not isinstance(buf, (bytes, bytearray)) else list(buf)
            for v in vals:
                nib = int(v) & 0xF
                self._cs_total_words += 1
                if self._cs_total_words == 1:
                    self._4bit_strobe_candidate = (direction, nib)
                    self._8bit_strobe_candidate = (direction, nib, None)
                    self._8bit_register_candidate = (direction, nib, None)
                    self._first_result_start = frame.start_time
                elif self._cs_total_words == 2:
                    if nib == 0x0:
                        self._8bit_strobe_candidate = (direction, self._8bit_strobe_candidate[1], 0)
                    else:
                        self._8bit_strobe_candidate = None
                    self._8bit_register_candidate = (direction, self._8bit_register_candidate[1], nib)
                    self._first_result_start = frame.start_time
                self._last_result_end = frame.end_time

        return outputs if outputs else None
