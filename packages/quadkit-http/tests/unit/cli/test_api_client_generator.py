"""Tests for the API client generator."""

from __future__ import annotations

from quadkit.http.cli.generators.api_client import APIClientGenerator


def _gen(tmp_path) -> APIClientGenerator:
    return APIClientGenerator(output_dir=tmp_path / "clients")


class TestAPIClientGenerator:
    def test_metadata(self, tmp_path) -> None:
        g = _gen(tmp_path)
        assert g.name == "api_client"
        assert g.description == "Generate an external API client"

    def test_dry_run_writes_nothing(self, tmp_path) -> None:
        g = _gen(tmp_path)
        result = g.generate("Stripe", dry_run=True)
        assert result.files_created
        assert not (tmp_path / "clients" / "stripe_client.py").exists()

    def test_generate_writes_client_module(self, tmp_path) -> None:
        g = _gen(tmp_path)
        result = g.generate("Stripe")
        path = tmp_path / "clients" / "stripe_client.py"
        assert path.exists()
        content = path.read_text()
        assert "StripeClient" in content
        # default fields
        assert "base_url" in content
        assert "api_key" in content
        assert len(result.files_created) == 1

    def test_generate_with_custom_fields(self, tmp_path) -> None:
        g = _gen(tmp_path)
        g.generate("Payments", fields_str="endpoint:str, token:str")
        content = (tmp_path / "clients" / "payments_client.py").read_text()
        assert "endpoint" in content
        assert "token" in content
        assert "PaymentsClient" in content

    def test_fields_str_invalid_raises(self, tmp_path) -> None:
        import pytest

        g = _gen(tmp_path)
        with pytest.raises(ValueError, match="Invalid field"):
            g.generate("Payments", fields_str="endpoint: str")

    def test_generate_idempotent_without_force(self, tmp_path) -> None:
        g = _gen(tmp_path)
        first = g.generate("Stripe")
        assert first.files_created
        second = g.generate("Stripe")
        assert not second.files_created
        assert second.files_skipped

    def test_generate_force_overwrites(self, tmp_path) -> None:
        g = _gen(tmp_path)
        g.generate("Stripe")
        third = g.generate("Stripe", force=True)
        assert third.files_overwritten

    def test_pascal_and_snake_casing(self, tmp_path) -> None:
        g = _gen(tmp_path)
        g.generate("my_client")
        assert (tmp_path / "clients" / "my_client_client.py").exists()
        content = (tmp_path / "clients" / "my_client_client.py").read_text()
        assert "MyClientClient" in content

    def test_auth_option_forwarded(self, tmp_path) -> None:
        g = _gen(tmp_path)
        g.generate("OAuth", auth="oauth")
        # snake_case of "OAuth" is "o_auth"; file is written and non-empty
        content = (tmp_path / "clients" / "o_auth_client.py").read_text()
        assert "OAuthClient" in content

    def test_name_sanitization(self, tmp_path) -> None:
        g = _gen(tmp_path)
        assert g._to_pascal_case("stripe_api") == "StripeApi"
        assert g._to_snake_case("StripeApi") == "stripe_api"
        assert g._to_pascal_case("my_client") == "MyClient"
