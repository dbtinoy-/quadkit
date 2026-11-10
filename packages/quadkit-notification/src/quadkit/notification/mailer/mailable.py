"""Mailable — base class for structured email templates."""

from __future__ import annotations

import abc
import html

from quadkit.contracts.mailer import EmailMessage


class Mailable(abc.ABC):
    """Base class for structured email templates.

    Subclass ``Mailable`` to encapsulate the data and rendering logic for a
    specific email type. Call :meth:`to_message` to build the
    :class:`~quadkit.contracts.mailer.types.EmailMessage` that is
    passed to :meth:`~quadkit.contracts.mailer.protocols.MailerProtocol.send`.

    Example::

        class WelcomeMail(Mailable):
            def __init__(self, user_name: str, user_email: str) -> None:
                self.user_name = user_name
                self.user_email = user_email

            def to_message(self) -> EmailMessage:
                return EmailMessage(
                    to=[self.user_email],
                    subject=f"Welcome, {self.user_name}!",
                    body=f"Hi {self.user_name}, welcome aboard.",
                    html_body=f"<p>Hi <b>{escape_html(self.user_name)}</b>, welcome aboard.</p>",
                )
    """

    @abc.abstractmethod
    def to_message(self) -> EmailMessage:
        """Build the EmailMessage for this mailable.

        Returns:
            A fully populated :class:`~quadkit.contracts.mailer.types.EmailMessage`.
        """


def escape_html(text: str) -> str:
    """Escape text for inclusion in an HTML email body.

    HTML email bodies are rendered by mail clients; user-controlled text
    interpolated unescaped (as in the pre-fix docstring example) becomes
    markup. Escape before building ``html_body``.

    Args:
        text: Untrusted text, e.g. a user-entered name.

    Returns:
        Text with ``&``, ``<``, ``>``, and ``"`` escaped so it renders as
        literal text in an HTML email.
    """
    return html.escape(text, quote=True)


__all__ = ["Mailable", "escape_html"]
