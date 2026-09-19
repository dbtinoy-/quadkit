"""Secret registration surface for :class:`~quadkit.app.base.Application`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.config import QuadkitConfig


class SecretsMixin:
    """Registers literal and store-backed secrets for pre-boot validation.

    State attributes (``_registered_secrets``, ``_secrets_from_stores``,
    ``_secrets_policy``) are owned by ``Application.__init__``.
    """

    if TYPE_CHECKING:
        _config: QuadkitConfig
        _logger: Any
        name: str
        _registered_secrets: dict[str, str]
        _secrets_from_stores: list[tuple[Any, list[str]]]
        _secrets_policy: Any | None

    def register_secrets(
        self,
        secrets: dict[str, str],
        *,
        policy: Any | None = None,
    ) -> None:
        """Register secrets to be validated before providers boot.

        The framework validates these secrets during :meth:`start`, before any
        provider's ``register()`` is called.  The app declares *what* to
        validate; the framework supplies the logic via
        :class:`~quadkit.config.secrets.SecretsValidator`.

        Args:
            secrets: Mapping of secret name → value.  Names should be
                descriptive (e.g. ``"JWT_SECRET"``), as they appear in
                error messages.
            policy: Optional :class:`~quadkit.config.secrets.SecretsPolicy`
                that controls strictness.  When ``None`` a default policy is
                derived from the active
                :class:`~quadkit.contracts.core.config.Environment`.

        Example::

            app.register_secrets(
                {
                    "JWT_SECRET": os.environ["JWT_SECRET"],
                    "OAUTH_CLIENT_SECRET": os.environ["OAUTH_CLIENT_SECRET"],
                },
            )
        """
        self._registered_secrets.update(secrets)
        if policy is not None:
            self._secrets_policy = policy

    def register_secrets_from_store(
        self,
        store: Any,
        secret_names: list[str],
        *,
        policy: Any | None = None,
    ) -> None:
        """Register secrets sourced from a SecretStore to be validated before providers boot.

        The framework validates these secrets during :meth:`start`, before any
        provider's ``register()`` is called. Secrets are retrieved from the store
        at validation time and validated using the same
        :class:`~quadkit.config.secrets.SecretsValidator` logic as literal secrets.

        Args:
            store: An implementation of
                :class:`~quadkit.contracts.security.secrets.SecretStoreProtocol`.
            secret_names: List of secret names to retrieve from the store.
                Names should be descriptive (e.g. ``"JWT_SECRET"``), as they
                appear in error messages.
            policy: Optional :class:`~quadkit.config.secrets.SecretsPolicy`
                that controls strictness. When ``None`` a default policy is
                derived from the active
                :class:`~quadkit.contracts.core.config.Environment`.

        Raises:
            SecretNotFoundError: In strict mode, if any secret is not found in
                the store. In non-strict mode, missing secrets are logged as
                warnings and boot continues.

        Example::

            from quadkit.security.secrets import EnvSecretStore

            app.register_secrets_from_store(
                EnvSecretStore(),
                ["NEXTAUTH_SECRET", "DATABASE_PASSWORD"],
            )
        """
        self._secrets_from_stores.append((store, secret_names))
        if policy is not None:
            self._secrets_policy = policy

    def _validate_secrets(self) -> None:
        """Run boot-time secrets validation.

        Uses the policy stored on this instance (or derives a default from the
        active environment) to validate all secrets registered via
        :meth:`register_secrets` and :meth:`register_secrets_from_store`.
        """
        from quadkit.config.secrets import SecretsPolicy, SecretsValidator

        if self._secrets_policy is not None:
            policy = self._secrets_policy
        else:
            policy = SecretsPolicy.for_environment(self._config.env)

        # Collect all secrets (literals + from stores)
        all_secrets: dict[str, str] = dict(self._registered_secrets)

        # Pull secrets from stores
        for store, secret_names in self._secrets_from_stores:
            for name in secret_names:
                try:
                    value = store.get_secret(name)
                    all_secrets[name] = value
                except Exception:  # noqa: BLE001 — a missing secret or a store driver failure degrades to empty (the validator still rejects empty values)
                    # Treat missing secrets from store like missing literal secrets
                    all_secrets[name] = ""

        validator = SecretsValidator(policy)
        total_count = len(all_secrets)
        self._logger.info(
            "application.secrets_validation",
            name=self.name,
            secret_count=total_count,
            strict=policy.strict,
        )
        validator.validate(all_secrets)
