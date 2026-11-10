"""Mailer submodule — email delivery backends, mailable base, and IoC module."""

from __future__ import annotations

from quadkit.notification.mailer.mailable import Mailable
from quadkit.notification.mailer.module import MailerModule
from quadkit.notification.mailer.retrying_mailer import RetryingMailer
from quadkit.notification.mailer.runtime import MailerDeliveryRuntime
from quadkit.notification.mailer.sendgrid_mailer import SendGridMailer
from quadkit.notification.mailer.smtp_mailer import SMTPMailer

__all__ = [
    "Mailable",
    "MailerDeliveryRuntime",
    "MailerModule",
    "RetryingMailer",
    "SMTPMailer",
    "SendGridMailer",
]
