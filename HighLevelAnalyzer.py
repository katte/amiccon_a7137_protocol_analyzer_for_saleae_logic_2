# HighLevelAnalyzer.py (CS-single-word, 4-bit assumed, monotonic emission)
# - SPI always 4-bit (assumed).
# - Emit a strobe only if exactly one data word (MOSI/MISO according to 'source')
#   is received between CS enable and CS disable.
# - Does NOT emit 'cs' frames to avoid ordering issues.
# - Ensures that the begin time of emitted frames is strictly increasing.

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, ChoicesSetting

_STROBE_MAP = {
    0x8: 'Strobe: SleepMode',
    0x9: 'Strobe: Idle Mode',
    0xA: 'Strobe: Standby Mode',
    0xB: 'Strobe: PLL Mode',
    0xC: 'Strobe: RX Mode',
    0xD: 'Strobe: TX Mode',
    0xE: 'Strobe: Fifo Write Pointer Reset',
    0xF: 'Strobe: Fifo Read Pointer Reset',
}

def _as_bool(choice: str) -> bool:
    return str(choice).lower() in ('true','yes','on','1')

class Amiccon_A7137_ProtocolAnalyzerHLA(HighLevelAnalyzer):
    source = ChoicesSetting(['MOSI', 'MISO', 'Both'])
    require_cs_choice = ChoicesSetting(['True','False'])
    emit_debug_choice = ChoicesSetting(['False','True'])

    result_types = {
        'strobe': {'format': '{{data.dir}}: {{data.name}} (val={{data.val}})'},
        'debug':  {'format': '{{data.dir}} {{data.msg}}'}
    }

    def __init__(self):
        self.cs_asserted = False
        self._cs_total_words = 0
        self._cs_candidate = None      # (direction, nibble)
        self._first_result_start = None
        self._last_result_end = None
        self._last_emitted_begin = None  # to maintain monotonicity

    def _reset_cs(self):
        self._cs_total_words = 0
        self._cs_candidate = None
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
        require_cs = _as_bool(getattr(self, 'require_cs_choice', 'True'))
        emit_debug = _as_bool(getattr(self, 'emit_debug_choice', 'False'))

        if frame.type == 'enable':
            self.cs_asserted = True
            self._reset_cs()
            return None  # no 'cs' frame

        if frame.type == 'disable':
            # Emit conditionally as strobe only (no 'cs')
            if self._cs_total_words == 1 and self._cs_candidate is not None:
                direction, nib = self._cs_candidate
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

                name = _STROBE_MAP.get(nib)
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

            self.cs_asserted = False
            self._reset_cs()
            return out

        if frame.type != 'result':
            return None

        if require_cs and not self.cs_asserted:
            return None

        # Streams
        streams = []
        if self.source in ('MOSI', 'Both'):
            if 'mosi' in frame.data and frame.data['mosi'] is not None:
                streams.append(('MOSI', frame.data['mosi']))
        if self.source in ('MISO', 'Both'):
            if 'miso' in frame.data and frame.data['miso'] is not None:
                streams.append(('MISO', frame.data['miso']))

        if not streams:
            return None

        outputs = []

        for direction, buf in streams:
            vals = list(buf) if not isinstance(buf, (bytes, bytearray)) else list(buf)
            for v in vals:
                nib = int(v) & 0xF
                self._cs_total_words += 1
                if self._cs_total_words == 1:
                    self._cs_candidate = (direction, nib)
                    self._first_result_start = frame.start_time
                self._last_result_end = frame.end_time

                if emit_debug:
                    # debug uses the current frame times; make sure we don't go backwards
                    start_t = frame.start_time
                    end_t = frame.end_time
                    span = end_t - start_t
                    start_t, end_t = self._monotonic_times(start_t, end_t, span)
                    outputs.append(AnalyzerFrame('debug', start_t, end_t, {
                        'dir': direction,
                        'msg': f'4b_seen=0x{nib:X} (count={self._cs_total_words})'
                    }))

        return outputs if outputs else None
