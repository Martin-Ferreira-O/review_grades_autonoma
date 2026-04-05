import math
import time

import pyotp


class TotpCodeProvider:
    def __init__(self, secret: str):
        normalized_secret = secret.strip().replace(" ", "").replace("-", "").upper()
        self._totp = pyotp.TOTP(normalized_secret)

    def current_code(self, *, at_time: float | None = None) -> str:
        if at_time is None:
            return self._totp.now()
        return self._totp.at(int(at_time))

    def seconds_remaining(self, *, at_time: float | None = None) -> int:
        now = time.time() if at_time is None else at_time
        interval = int(self._totp.interval)
        remaining = interval - (now % interval)
        return max(1, int(math.ceil(remaining)))
