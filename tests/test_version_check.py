"""Tests for runtime version sync check."""

import json
from unittest.mock import MagicMock, patch

from openubl.version import check_api_version
from openubl import __version__


class TestVersionCheck:
    def test_check_api_version_matches(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"version": __version__}).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("openubl.version.urllib.request.urlopen", return_value=mock_response):
            result = check_api_version()

        assert result["ok"] is True
        assert result["sdk_version"] == __version__
        assert result["api_version"] == __version__

    def test_check_api_version_mismatch(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"version": "99.99.99"}).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("openubl.version.urllib.request.urlopen", return_value=mock_response):
            result = check_api_version()

        assert result["ok"] is False
        assert result["sdk_version"] == __version__
        assert result["api_version"] == "99.99.99"
