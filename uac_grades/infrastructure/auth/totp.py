import pyotp


class TotpCodeProvider:
    def __init__(self, secret: str):
        self._totp = pyotp.TOTP(secret)

    def current_code(self) -> str:
        return self._totp.now()
