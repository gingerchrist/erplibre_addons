from odoo import _, api, fields, models


class ItCodeGeneratorModuleModelField(models.Model):
    _name = "it.code_generator.module.model.field"
    _description = "it_code_generator_module_model_field"

    name = fields.Char()

    help = fields.Char()

    has_error = fields.Boolean(compute="_compute_has_error", store=True)

    model_id = fields.Many2one(
        comodel_name="it.code_generator.module.model",
        string="Model",
        ondelete="cascade",
    )

    type = fields.Selection(
        selection=[
            ("char", "char"),
            ("boolean", "boolean"),
            ("integer", "integer"),
            ("float", "float"),
            ("text", "text"),
            ("html", "html"),
            ("datetime", "datetime"),
            ("date", "date"),
            ("many2one", "many2one"),
            ("many2many", "many2many"),
            ("one2many", "one2many"),
        ],
        required=True,
    )

    relation = fields.Many2one(
        string="Comodel",
        comodel_name="it.code_generator.module.model",
        help="comodel - Create relation for many2one, many2many, one2many",
    )

    relation_manual = fields.Char(
        string="Comodel manual",
        help=(
            "comodel - Create relation for many2one, many2many, one2many."
            " Manual entry by pass relation field."
        ),
    )

    field_relation = fields.Many2one(
        string="Inverse field",
        comodel_name="it.code_generator.module.model.field",
        domain="[('model_id', '=', relation)]",
        help="inverse_name - Need for one2many to associate with many2one.",
    )

    field_relation_manual = fields.Char(
        string="Inverse field manual",
        help=(
            "inverse_name - Need for one2many to associate with many2one,"
            " manual entry."
        ),
    )

    widget = fields.Selection(
        selection=[
            ("image", "image"),
            ("many2many_tags", "many2many_tags"),
            ("priority", "priority"),
            ("selection", "selection"),
            ("mail_followers", "mail_followers"),
            ("mail_activity", "mail_activity"),
            ("mail_thread", "mail_thread"),
        ]
    )

    it_workspace_ids = fields.Many2many(
        comodel_name="it.workspace",
        string="It Workspace",
    )

    @api.depends(
        "type",
        "relation",
        "relation_manual",
        "field_relation",
        "field_relation_manual",
    )
    def _compute_has_error(self):
        for rec in self:
            # Disable all error
            rec.has_error = False
            if rec.type in ("many2many", "many2one", "one2many"):
                has_relation = rec.relation or rec.relation_manual
                has_field_relation = True
                if rec.type == "one2many":
                    has_field_relation = (
                        rec.field_relation or rec.field_relation_manual
                    )
                rec.has_error = not has_relation or not has_field_relation
