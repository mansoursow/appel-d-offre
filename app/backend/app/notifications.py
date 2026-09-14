"""
Envoi des e-mails de notification.

Un seul evenement notifie pour l'instant : un avis vient d'etre RETENU (ou
confie a un nouveau responsable). Le responsable du montage recoit un e-mail
lui indiquant qu'un dossier l'attend sur le site ; si personne n'est encore
designe, tous les comptes "montage" actifs sont prevenus.

L'envoi part en tache de fond, apres la reponse HTTP : un service de mail lent
ou en panne ne bloque jamais l'enregistrement de la decision. Le resultat
(envoye / echec) est trace dans le journal d'activite de l'administrateur.

Transport, dans cet ordre (voir config.py) : Brevo, Resend, SMTP.
"""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from email.utils import parseaddr

import requests

from . import auth, config
from .database import SessionLocal
from .models import Selection, User

logger = logging.getLogger("uvicorn.error")


def is_configured() -> bool:
    return bool(config.EMAIL_FROM and (config.BREVO_API_KEY or config.RESEND_API_KEY or config.SMTP_HOST))


def send_email(to: list[str], subject: str, text_body: str, html_body: str) -> None:
    """Envoie un e-mail. Leve une exception en cas d'echec."""
    if not is_configured():
        raise RuntimeError("aucun service d'envoi configuré")
    if config.BREVO_API_KEY:
        _send_brevo(to, subject, text_body, html_body)
    elif config.RESEND_API_KEY:
        _send_resend(to, subject, text_body, html_body)
    else:
        _send_smtp(to, subject, text_body, html_body)


def _send_brevo(to, subject, text_body, html_body):
    name, address = parseaddr(config.EMAIL_FROM)
    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": config.BREVO_API_KEY, "accept": "application/json"},
        json={
            "sender": {"email": address, **({"name": name} if name else {})},
            "to": [{"email": addr} for addr in to],
            "subject": subject,
            "textContent": text_body,
            "htmlContent": html_body,
        },
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Brevo {resp.status_code} : {resp.text[:200]}")


def _send_resend(to, subject, text_body, html_body):
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
        json={"from": config.EMAIL_FROM, "to": to, "subject": subject, "text": text_body, "html": html_body},
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Resend {resp.status_code} : {resp.text[:200]}")


def _send_smtp(to, subject, text_body, html_body):
    msg = EmailMessage()
    msg["From"] = config.EMAIL_FROM
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    context = ssl.create_default_context()
    if config.SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20, context=context)
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
        server.starttls(context=context)
    with server:
        if config.SMTP_USER:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)


# --------------------------------------------------------------------------
# Avis retenu -> responsable du montage
# --------------------------------------------------------------------------
def notify_dossier_assigned(selection_id: int) -> None:
    """Tache de fond : previent le(s) responsable(s) du montage d'un avis retenu."""
    if not is_configured():
        return
    with SessionLocal() as db:
        selection = db.get(Selection, selection_id)
        if selection is None or selection.decision != "retenu":
            return

        if selection.assigned_to is not None:
            recipients = [selection.assigned_to] if selection.assigned_to.is_active else []
        else:
            recipients = db.query(User).filter(User.role == "monteur", User.is_active.is_(True)).all()
        addresses = sorted({u.email for u in recipients if u.email})

        if not addresses:
            names = ", ".join(u.full_name or u.username for u in recipients) or "aucun compte montage actif"
            _log(db, selection, "notification_non_envoyee", f"aucune adresse e-mail renseignee ({names})")
            return

        subject, text_body, html_body = _dossier_message(selection)
        try:
            send_email(addresses, subject, text_body, html_body)
        except Exception as exc:
            logger.error("Notification e-mail du dossier %s en echec : %s", selection.id, exc)
            _log(db, selection, "notification_echec", f"{', '.join(addresses)} : {str(exc)[:200]}")
            return
        _log(db, selection, "notification_envoyee", ", ".join(addresses))


def _log(db, selection: Selection, action: str, detail: str) -> None:
    auth.log_activity(db, None, action, target_type="selection", target_id=selection.id,
                      detail=f"{selection.title[:100]} -> {detail}")
    db.commit()


def _dossier_message(selection: Selection) -> tuple[str, str, str]:
    deadline_line = "Date limite : non renseignée"
    if selection.deadline_iso:
        try:
            deadline = date.fromisoformat(selection.deadline_iso[:10])
            days_left = (deadline - date.today()).days
            when = (f"dans {days_left} jour(s)" if days_left >= 0 else f"dépassée de {-days_left} jour(s)")
            deadline_line = f"Date limite : {deadline.strftime('%d/%m/%Y')} ({when})"
        except ValueError:
            deadline_line = f"Date limite : {selection.deadline_iso}"

    selected_by = selection.selected_by.full_name or selection.selected_by.username if selection.selected_by else None
    assignee = selection.assigned_to
    greeting = f"Bonjour {assignee.full_name or assignee.username}," if assignee else "Bonjour,"
    intro = (
        "Un avis vient d'être retenu et le montage du dossier vous est confié."
        if assignee else
        "Un avis vient d'être retenu. Aucun responsable du montage n'est encore désigné."
    )

    lines = [
        ("Avis", selection.title),
        ("Organisme", selection.entity),
        (None, deadline_line),
        ("Retenu par", selected_by),
        ("Commentaire", selection.comment),
        ("Annonce d'origine", selection.url),
    ]
    subject = f"Dossier à monter : {selection.title[:90]}"

    text_parts = [greeting, "", intro, ""]
    for label, value in lines:
        if value:
            text_parts.append(f"{label} : {value}" if label else value)
    text_parts += [
        "",
        "À faire : joindre l'offre technique et l'offre financière avant la date limite.",
        f"Ouvrir le site (onglet Dossiers) : {config.APP_PUBLIC_URL}",
    ]

    rows = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#6b7280;vertical-align:top'>{html.escape(label)}</td>"
        f"<td style='padding:4px 0'>{_html_value(label, value)}</td></tr>"
        if label else
        f"<tr><td style='padding:4px 12px 4px 0;color:#6b7280'>Date limite</td>"
        f"<td style='padding:4px 0'><strong>{html.escape(value.split(' : ', 1)[1])}</strong></td></tr>"
        for label, value in lines if value
    )
    html_body = f"""
<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#1f2937;max-width:600px">
  <p>{html.escape(greeting)}</p>
  <p>{html.escape(intro)}</p>
  <table style="border-collapse:collapse;margin:12px 0">{rows}</table>
  <p>À faire : joindre <strong>l'offre technique</strong> et <strong>l'offre financière</strong> avant la date limite.</p>
  <p><a href="{html.escape(config.APP_PUBLIC_URL)}"
        style="display:inline-block;background:#0a2f73;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none">
     Ouvrir le site (onglet Dossiers)</a></p>
</div>"""
    return subject, "\n".join(text_parts), html_body


def _html_value(label: str, value: str) -> str:
    if label == "Annonce d'origine" and value.startswith("http"):
        return f"<a href='{html.escape(value)}'>{html.escape(value)}</a>"
    return html.escape(value)
