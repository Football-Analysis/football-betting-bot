import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import Iterable, Optional, Sequence, Tuple


class MailClient:
    """
    A simple SMTP mail client that connects and authenticates on initialization.
    Defaults target Gmail's SSL endpoint, but works with any SMTP server.
    """

    def __init__(
        self,
        username: str,
        password: str,
        host: str = "smtp.gmail.com",
        port: int = 465,
        use_ssl: bool = True,
        timeout: int = 20,
        max_retries: int = 3,
    ):
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.timeout = timeout
        self.max_retries = max_retries
        self._server: Optional[smtplib.SMTP] = None

        self._connect_and_login()

    def _connect_and_login(self) -> None:
        """Connects and logs in immediately."""
        context = ssl.create_default_context()
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.use_ssl:
                    server = smtplib.SMTP_SSL(
                        self.host, self.port, timeout=self.timeout, context=context
                    )
                else:
                    server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                    server.starttls(context=context)

                server.login(self.username, self.password)
                self._server = server
                return
            except Exception as e:
                # Ensure server is closed on failure
                try:
                    server.quit()
                except Exception:
                    pass

                if attempt == self.max_retries:
                    raise
                time.sleep(2 ** attempt)  # backoff
                #print("nooooooo")

    def close(self) -> None:
        if self._server is not None:
            try:
                self._server.quit()
            finally:
                self._server = None

    def __enter__(self):
        # Already connected in __init__
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _ensure_connected(self):
        if self._server is None:
            self._connect_and_login()
            return
        try:
            code = self._server.noop()[0]
            if code != 250:
                raise smtplib.SMTPServerDisconnected("NOOP not 250")
        except Exception:
            # stale or dropped connection; rebuild
            try: self.close()
            except Exception: pass
            self._connect_and_login()

    def send_mail(
        self,
        subject: str,
        to: Iterable[str],
        text_body: str,
        html_body: Optional[str] = None,
        *,
        cc: Optional[Iterable[str]] = None,
        bcc: Optional[Iterable[str]] = None,
        reply_to: Optional[str] = None,
        from_name: Optional[str] = "Post & In Alerts",
        custom_headers: Optional[dict] = None,
        send_retries: int = 3,
    ) -> None:
        """
        Send an email via the already-authenticated SMTP session.

        - If html_body is provided, sends multipart/alternative with text + HTML.
        - Attachments: list of (filename, bytes_content, maintype, subtype), e.g. ("report.csv", b"...", "text", "csv")
        """
        self._ensure_connected()

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{self.username}>" if from_name else self.username
        msg["To"] = ", ".join(to)

        if cc:
            msg["Cc"] = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to
        if custom_headers:
            for k, v in custom_headers.items():
                msg[k] = v

        # Build body
        if html_body:
            msg.set_content(text_body or " ")
            msg.add_alternative(html_body, subtype="html")
        else:
            msg.set_content(text_body)

        all_recipients = list(to) + (list(cc) if cc else []) + (list(bcc) if bcc else [])

        # Retry send; if server drops, reconnect once per attempt
        last_exc = None
        for attempt in range(1, max(1, send_retries) + 1):
            try:
                self._server.send_message(msg, to_addrs=all_recipients)
                return
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPDataError,
                    smtplib.SMTPConnectError, smtplib.SMTPHeloError,
                    smtplib.SMTPAuthenticationError, TimeoutError) as e:
                last_exc = e
                # Try to transparently reconnect before next attempt
                try:
                    self.close()
                except Exception:
                    pass
                if attempt == send_retries:
                    break
                time.sleep(2 ** attempt)
                self._connect_and_login()

        raise RuntimeError(f"Failed to send email after {send_retries} attempts: {last_exc}")
