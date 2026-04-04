"""Tests for TfContext resolution from environment variables."""

import pytest
import tf


class TestTfContextFromEnvironment:
    def test_reads_profile_from_aws_vault(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        monkeypatch.delenv("environment", raising=False)

        ctx = tf.TfContext.from_environment()

        assert ctx.profile == "staging"

    def test_reads_profile_from_environment_when_aws_vault_not_set(self, monkeypatch):
        monkeypatch.delenv("AWS_VAULT", raising=False)
        monkeypatch.setenv("environment", "prod")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        ctx = tf.TfContext.from_environment()

        assert ctx.profile == "prod"

    def test_aws_vault_takes_precedence_over_environment(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("environment", "prod")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        ctx = tf.TfContext.from_environment()

        assert ctx.profile == "staging"

    def test_reads_region_from_aws_default_region(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        monkeypatch.delenv("AWS_REGION", raising=False)

        ctx = tf.TfContext.from_environment()

        assert ctx.region == "eu-west-1"

    def test_reads_region_from_aws_region_as_fallback(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.setenv("AWS_REGION", "us-east-1")

        ctx = tf.TfContext.from_environment()

        assert ctx.region == "us-east-1"

    def test_aws_default_region_takes_precedence_over_aws_region(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        monkeypatch.setenv("AWS_REGION", "us-east-1")

        ctx = tf.TfContext.from_environment()

        assert ctx.region == "eu-west-1"

    def test_error_when_no_profile_set(self, monkeypatch):
        monkeypatch.delenv("AWS_VAULT", raising=False)
        monkeypatch.delenv("environment", raising=False)
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

        with pytest.raises(tf.TfError, match="No profile found"):
            tf.TfContext.from_environment()

    def test_error_when_no_region_set(self, monkeypatch):
        monkeypatch.setenv("AWS_VAULT", "staging")
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)

        with pytest.raises(tf.TfError, match="No region found"):
            tf.TfContext.from_environment()
