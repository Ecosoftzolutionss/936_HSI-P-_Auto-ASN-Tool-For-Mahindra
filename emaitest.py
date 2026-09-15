import poplib
import email
import re
from email.header import decode_header, make_header

from config import (
    OTP_MAIL_SERVER,
    OTP_MAIL_USERNAME,
    OTP_MAIL_PASSWORD,
    OTP_SENDER,
    OTP_SUBJECT,
)


# ================================================================
# POP3 CONFIGURATION
# ================================================================
# POP3 uses port 995.
# Dashboard IMAP connection can continue using port 993.
OTP_POP3_PORT = 995


def decode_email_header(value):
    """
    Decode email Subject / From headers safely.
    """
    if not value:
        return ""

    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def extract_email_body(msg):
    """
    Extract plain-text body from an email.
    """

    body = ""

    try:

        if msg.is_multipart():

            for part in msg.walk():

                content_type = part.get_content_type()
                content_disposition = str(
                    part.get("Content-Disposition", "")
                )

                # Ignore attachments
                if "attachment" in content_disposition.lower():
                    continue

                if content_type == "text/plain":

                    payload = part.get_payload(
                        decode=True
                    )

                    if payload:

                        charset = (
                            part.get_content_charset()
                            or "utf-8"
                        )

                        body += payload.decode(
                            charset,
                            errors="ignore"
                        )

        else:

            payload = msg.get_payload(
                decode=True
            )

            if payload:

                charset = (
                    msg.get_content_charset()
                    or "utf-8"
                )

                body = payload.decode(
                    charset,
                    errors="ignore"
                )

    except Exception as ex:

        print(
            "Error while reading email body:",
            ex
        )

    return body


def is_msetu_otp_email(subject, sender):
    """
    Check whether the email is an MSetu OTP email.
    """

    subject = subject.lower()
    sender = sender.lower()

    expected_subject = OTP_SUBJECT.lower()
    expected_sender = OTP_SENDER.lower()

    return (
        expected_subject in subject
        or expected_sender in sender
    )


def extract_otp(body):
    """
    Extract a 6-digit OTP from email body.
    """

    if not body:
        return None

    otp_match = re.search(
        r"\b\d{6}\b",
        body
    )

    if otp_match:
        return otp_match.group(0)

    return None


def get_latest_otp():
    """
    Connect to POP3 mailbox and find the latest MSetu OTP email.
    """

    mail = None

    try:

        print("--------------------------------")
        print("Connecting to mail server...")
        print("Server:", OTP_MAIL_SERVER)
        print("Port:", OTP_POP3_PORT)
        print("--------------------------------")

        mail = poplib.POP3_SSL(
            OTP_MAIL_SERVER,
            OTP_POP3_PORT,
            timeout=30
        )

        # ============================================================
        # LOGIN
        # ============================================================

        mail.user(
            OTP_MAIL_USERNAME
        )

        mail.pass_(
            OTP_MAIL_PASSWORD
        )

        print(
            "Mail login successful."
        )

        # ============================================================
        # GET EMAIL COUNT
        # ============================================================

        response, messages, octets = mail.list()

        total_emails = len(messages)

        print(
            "Total emails:",
            total_emails
        )

        if total_emails == 0:

            print(
                "Mailbox is empty."
            )

            return None

        # ============================================================
        # SEARCH FROM LATEST EMAIL
        # ============================================================

        for mail_no in range(
            total_emails,
            0,
            -1
        ):

            print(
                f"Checking email {mail_no}/{total_emails}..."
            )

            try:

                response, lines, octets = mail.retr(
                    mail_no
                )

                raw_email = b"\r\n".join(
                    lines
                )

                msg = email.message_from_bytes(
                    raw_email
                )

                # ====================================================
                # SUBJECT
                # ====================================================

                subject = decode_email_header(
                    msg.get("Subject", "")
                )

                # ====================================================
                # SENDER
                # ====================================================

                sender = decode_email_header(
                    msg.get("From", "")
                )

                print(
                    "Subject:",
                    subject
                )

                print(
                    "From:",
                    sender
                )

                # ====================================================
                # CHECK MSETU OTP EMAIL
                # ====================================================

                if not is_msetu_otp_email(
                    subject,
                    sender
                ):

                    continue

                print(
                    "MSetu OTP email found."
                )

                # ====================================================
                # EXTRACT BODY
                # ====================================================

                body = extract_email_body(
                    msg
                )

                # ====================================================
                # EXTRACT OTP
                # ====================================================

                otp = extract_otp(
                    body
                )

                if otp:

                    print("--------------------------------")
                    print(
                        "LATEST OTP:",
                        otp
                    )
                    print("--------------------------------")

                    return otp

            except Exception as ex:

                print(
                    f"Error reading email {mail_no}:",
                    ex
                )

                continue

        print(
            "No OTP email found."
        )

        return None

    except poplib.error_proto as ex:

        print("--------------------------------")
        print("POP3 ERROR")
        print("--------------------------------")
        print(ex)

        return None

    except TimeoutError as ex:

        print("--------------------------------")
        print("MAIL SERVER CONNECTION TIMEOUT")
        print("--------------------------------")
        print(ex)

        return None

    except Exception as ex:

        print("--------------------------------")
        print("MAIL CONNECTION ERROR")
        print("--------------------------------")
        print(ex)

        return None

    finally:

        # ============================================================
        # CLOSE CONNECTION
        # ============================================================

        if mail is not None:

            try:
                mail.quit()

                print(
                    "Mail connection closed."
                )

            except Exception:
                pass


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("")
    print("========================================")
    print("        MSetu OTP Mail Test")
    print("========================================")
    print("")

    otp = get_latest_otp()

    print("")

    if otp:

        print(
            "OTP retrieved successfully:",
            otp
        )

    else:

        print(
            "OTP could not be retrieved."
        )

    print("")
    print("========================================")