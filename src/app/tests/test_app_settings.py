from django.test import SimpleTestCase

from app.settings import parse_allowed_hosts


class AllowedHostsSettingTests(SimpleTestCase):
    def test_empty_allowed_hosts_returns_empty_list(self) -> None:
        self.assertEqual(parse_allowed_hosts(""), [])

    def test_blank_allowed_hosts_entries_are_ignored(self) -> None:
        self.assertEqual(
            parse_allowed_hosts("localhost,, 127.0.0.1, ,api.example.com,"),
            ["localhost", "127.0.0.1", "api.example.com"],
        )

    def test_wildcard_allowed_host_is_preserved(self) -> None:
        self.assertEqual(parse_allowed_hosts("*"), ["*"])
