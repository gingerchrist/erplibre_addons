from odoo import _, api, fields, models


class ItCodeGeneratorModuleModelField(models.Model):
    _name = "it.code_generator.module.model.field"
    _description = "it_code_generator_module_model_field"

    name = fields.Char()

    help = fields.Char()

    model_id = fields.Many2one(
        comodel_name="it.code_generator.module.model",
        string="Model",
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

    # TODO missing support relation
    relation = fields.Many2one(
        comodel_name="it.code_generator.module.model",
        help="comodel - Create relation for many2one, many2many, one2many",
    )

    relation_manual = fields.Char(
        help=(
            "comodel - Create relation for many2one, many2many, one2many."
            " Manual entry by pass relation field."
        )
    )

    field_relation = fields.Many2one(
        comodel_name="it.code_generator.module.model.field",
        domain="[('model_id', '=', relation)]",
        help="inverse_name - Need for one2many to associate with many2one.",
    )

    field_relation_manual = fields.Char(
        help=(
            "inverse_name - Need for one2many to associate with many2one,"
            " manual entry."
        )
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
