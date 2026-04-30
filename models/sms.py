"""SMS routing and dispatch for CampScout.

Multi-provider routing: UA phones (+38x) → TurboSMS, PL phones (+48x) → secondary.
Uses fayna.sms.provider if fayna_sms_base is installed; falls back to Odoo native sms.sms.

TZ §23: SMS Multi-Provider Routing.
"""
import hashlib
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _sanitize_phone(phone: str) -> str:
    if not phone:
        return ""
    cleaned = re.sub(r"\s+", "", phone)
    cleaned = re.sub(r"[^\d+]", "", cleaned)
    if cleaned and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    return cleaned


def _hash_phone(phone: str) -> str:
    """SHA-256 prefix of digit-only number for RODO-safe logging."""
    normalized = "".join(c for c in (phone or "") if c.isdigit())
    return "sha256:" + hashlib.sha256(normalized.encode()).hexdigest()[:12] + "..."


class CampSmsRoutingRule(models.Model):
    """Phone-prefix → provider routing rules.

    Evaluated in sequence order. First matching prefix wins.
    Example:
      +38  → turbosms  (UA numbers)
      +48  → smsapi    (PL numbers — future provider)
      *    → turbosms  (catch-all)
    """

    _name = "fayna.sms.routing.rule"
    _description = "SMS routing rule (prefix → provider)"
    _order = "sequence, id"

    name = fields.Char(
        required=True,
        string=_("Rule name"),
        help=_("Human label, e.g. 'Ukraine (TurboSMS)'."),
    )
    sequence = fields.Integer(
        default=10,
        string=_("Sequence"),
        help=_("Lower = higher priority. First matching rule is used."),
    )
    phone_prefix = fields.Char(
        string=_("Phone prefix"),
        help=_(
            "E.164 prefix to match (e.g. '+38' for Ukraine, '+48' for Poland).\n"
            "Leave empty to use this rule as the catch-all fallback."
        ),
    )
    provider_key = fields.Char(
        required=True,
        string=_("Provider key"),
        help=_(
            "Technical name of the SMS provider.\n"
            "If fayna_sms_base is installed: matches fayna.sms.provider name.\n"
            "Built-in values: 'turbosms'."
        ),
    )
    active = fields.Boolean(default=True, string=_("Active"))

    def _match(self, phone: str) -> bool:
        """Return True if this rule's prefix matches the given phone number."""
        if not self.phone_prefix:
            return True
        return (phone or "").startswith(self.phone_prefix)


class CampSmsDispatcher(models.AbstractModel):
    """Camp-wide SMS dispatch logic.

    Usage from any camp model:
        self.env['fayna.sms.dispatcher'].send(phone='+380501234567', body='Hello')

    Routes via fayna.sms.routing.rule → fayna.sms.provider (if available) or falls
    back to native Odoo sms.sms queue.
    """

    _name = "fayna.sms.dispatcher"
    _description = "Camp SMS dispatcher (multi-provider routing)"

    def send(self, phone: str, body: str, partner_id: int = None) -> dict:
        """Dispatch an SMS through the best matching provider.

        :param phone: E.164 phone number.
        :param body: Message text.
        :param partner_id: Optional res.partner id for log linking.
        :returns: {'success': bool, 'error': str|None, 'provider': str}
        """
        phone = _sanitize_phone(phone)
        if not phone:
            return {"success": False, "error": "Empty phone number.", "provider": None}

        rule = self._find_rule(phone)
        provider_key = rule.provider_key if rule else "turbosms"

        _logger.info(
            "fayna_campscout.sms: dispatch to %s via provider=%s rule=%s",
            _hash_phone(phone),
            provider_key,
            rule.name if rule else "fallback",
        )

        # Prefer fayna_sms_base if installed
        if "fayna.sms.provider" in self.env:
            return self._send_via_fayna_base(phone, body, provider_key)

        # Native Odoo sms.sms fallback
        return self._send_via_odoo_native(phone, body)

    def _find_rule(self, phone: str):
        """Return first active routing rule that matches this phone number."""
        rules = self.env["fayna.sms.routing.rule"].search([("active", "=", True)])
        for rule in rules:
            if rule._match(phone):
                return rule
        return None

    def _send_via_fayna_base(self, phone: str, body: str, provider_key: str) -> dict:
        """Dispatch via fayna.sms.provider model (fayna_sms_base module)."""
        provider = self.env["fayna.sms.provider"].search(
            [("name", "ilike", provider_key), ("active", "=", True)],
            limit=1,
        )
        if not provider:
            _logger.warning(
                "fayna_campscout.sms: provider '%s' not found, trying first active", provider_key
            )
            provider = self.env["fayna.sms.provider"].search([("active", "=", True)], limit=1)
        if not provider:
            return {"success": False, "error": "No active SMS provider configured.", "provider": None}

        result = provider.send_sms(phone, body)
        return {
            "success": result.get("success", False),
            "error": result.get("error"),
            "provider": provider.name,
        }

    def _send_via_odoo_native(self, phone: str, body: str) -> dict:
        """Queue via native Odoo sms.sms (requires Odoo 'sms' module)."""
        try:
            self.env["sms.sms"].create(
                {
                    "number": phone,
                    "body": body,
                    "state": "outgoing",
                }
            )
            return {"success": True, "error": None, "provider": "odoo_native"}
        except Exception as exc:  # noqa: BLE001 — fallback, unknown state
            _logger.error("fayna_campscout.sms: native sms.sms failed: %s", exc)
            return {"success": False, "error": str(exc), "provider": "odoo_native"}


class ResConfigSettings(models.TransientModel):
    """Camp SMS settings in Odoo Settings app."""

    _inherit = "res.config.settings"

    camp_sms_sender_name = fields.Char(
        string=_("SMS sender name"),
        config_parameter="fayna_campscout.sms_sender_name",
        help=_(
            "Sender ID shown on the recipient's phone (e.g. 'CampScout').\n"
            "Max 11 alphanumeric characters — carrier restriction."
        ),
    )
    camp_sms_enabled = fields.Boolean(
        string=_("Enable camp SMS notifications"),
        config_parameter="fayna_campscout.sms_enabled",
        help=_(
            "When enabled, camp events (auto-refusal, registration, reminders) "
            "trigger SMS notifications to parents."
        ),
    )


class CampSmsTemplate(models.Model):
    """Reusable SMS templates for camp notifications.

    Supports Jinja-style variables: {{ participant_name }}, {{ camp_name }},
    {{ date }}, {{ url }}.  Rendered via _render_body() before dispatch.
    """

    _name = "camp.sms.template"
    _description = "Camp SMS notification template"
    _order = "template_type, name"

    name = fields.Char(
        required=True,
        string=_("Template name"),
        help=_("Internal name, e.g. 'Auto-refusal (PL)'."),
    )
    template_type = fields.Selection(
        [
            ("auto_refusal", "Auto-refusal (unsigned qualification card)"),
            ("registration_confirm", "Registration confirmed"),
            ("payment_reminder", "Payment reminder"),
            ("reminder_7d", "Reminder — 7 days before camp"),
            ("reminder_3d", "Reminder — 3 days before camp"),
            ("emergency_parent", "Emergency — parent notification"),
            ("custom", "Custom"),
        ],
        required=True,
        default="custom",
        string=_("Type"),
        help=_("Determines when this template is used automatically."),
    )
    lang = fields.Selection(
        [("uk_UA", "Ukrainian"), ("pl_PL", "Polish"), ("en_US", "English")],
        required=True,
        default="pl_PL",
        string=_("Language"),
        help=_("Recipient language. Select PL for Polish parents, UA for Ukrainian."),
    )
    body = fields.Text(
        required=True,
        string=_("Message body"),
        help=_(
            "Template text. Available variables:\n"
            "  {{ participant_name }} — child's first name\n"
            "  {{ camp_name }}        — camp / event name\n"
            "  {{ date }}             — relevant date (camp start or deadline)\n"
            "  {{ url }}              — link to portal or document\n"
            "Keep under 160 chars to avoid multi-part SMS charges."
        ),
    )
    active = fields.Boolean(default=True, string=_("Active"))

    def _render_body(self, context_vars: dict) -> str:
        """Simple variable substitution — {{ var }} → value.

        :param context_vars: dict of variable name → value.
        :returns: Rendered string.
        """
        self.ensure_one()
        body = self.body or ""
        for key, value in context_vars.items():
            body = body.replace("{{" + key + "}}", str(value or ""))
            body = body.replace("{{ " + key + " }}", str(value or ""))
        return body

    @api.constrains("body")
    def _check_body_length(self):
        for tmpl in self:
            if tmpl.body and len(tmpl.body) > 1600:
                raise UserError(
                    _("SMS template body is too long (%(len)s chars). Maximum is 1600.")
                    % {"len": len(tmpl.body)}
                )
