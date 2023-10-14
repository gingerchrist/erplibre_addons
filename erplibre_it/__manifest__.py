# Copyright 2023 TechnoLibre inc. - Mathieu Benoit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "ERPLibre IT",
    "category": "Tools",
    "summary": "ERPLibre IT manage workspace to create new ERPLibre",
    "version": "12.0.1.0.0",
    "author": "Mathieu Benoit",
    "license": "AGPL-3",
    "website": "https://erplibre.ca",
    "depends": ["mail"],
    "external_dependencies": {
        "python": ["pysftp"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/mail_message_subtype.xml",
        "views/it_code_generator.xml",
        "views/it_code_generator_module.xml",
        "views/it_code_generator_module_model.xml",
        "views/it_code_generator_module_model_field.xml",
        "views/it_code_generator_new_project.xml",
        "views/it_db_image.xml",
        "views/it_workspace.xml",
        "views/it_system.xml",
        "views/menu.xml",
        "data/ir_cron.xml",
        "data/it_system.xml",
    ],
    "installable": True,
    "post_init_hook": "post_init_hook",
}
