from odoo import fields, models


class CampscoutPortalSession(models.Model):
    _name = "campscout.portal.session"
    _description = "Parent portal session tracking"
    _order = "last_activity desc"

    partner_id = fields.Many2one(
        "res.partner", required=True, ondelete="cascade", string="Parent"
    )

    children_count = fields.Integer(string="Children registered", readonly=True)

    last_login = fields.Datetime(string="Last login")
    last_activity = fields.Datetime(string="Last activity")

    active_camps = fields.Integer(
        string="Active camps", compute="_compute_active_camps"
    )

    unread_messages = fields.Integer(string="Unread messages")
    pending_actions = fields.Integer(string="Pending actions (docs to sign)")

    def _compute_active_camps(self):
        for record in self:
            record.active_camps = 0


class CampscoutPortalMenu(models.Model):
    _name = "campscout.portal.menu"
    _description = "Portal menu customization per region"
    _order = "sequence"

    region = fields.Char(required=True, string="Region (e.g. 'PL', 'UA')")
    sequence = fields.Integer(default=10)

    show_shop = fields.Boolean(default=True, string="Show camp shop?")
    show_stories = fields.Boolean(default=True, string="Show daily stories?")
    show_loyalty = fields.Boolean(default=True, string="Show loyalty program?")
    show_reviews = fields.Boolean(default=True, string="Show reviews?")
    show_blog = fields.Boolean(default=True, string="Show blog?")

    custom_links = fields.Text(string="Custom links (JSON)")
