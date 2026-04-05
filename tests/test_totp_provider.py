import unittest

from uac_grades.infrastructure.auth.totp import TotpCodeProvider


class TotpCodeProviderTests(unittest.TestCase):
    def test_current_code_normalizes_secret_with_spaces_and_hyphens(self) -> None:
        normalized = TotpCodeProvider("JBSWY3DPEHPK3PXP")
        formatted = TotpCodeProvider("JBSW Y3DP-EHPK3PXP")

        self.assertEqual(normalized.current_code(at_time=1_700_000_000), formatted.current_code(at_time=1_700_000_000))

    def test_seconds_remaining_uses_totp_interval_boundaries(self) -> None:
        provider = TotpCodeProvider("JBSWY3DPEHPK3PXP")

        self.assertEqual(provider.seconds_remaining(at_time=60), 30)
        self.assertEqual(provider.seconds_remaining(at_time=61), 29)
        self.assertEqual(provider.seconds_remaining(at_time=89.2), 1)


if __name__ == "__main__":
    unittest.main()
