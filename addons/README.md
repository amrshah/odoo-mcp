# Odoo Custom Addons

This directory is mounted to `/mnt/extra-addons` inside the Odoo 19 container.

## Adding Clinic / Hospital Modules
Place your custom or third-party healthcare modules here. For example:
- `clinic_base`: Clinic core settings, departments, rooms
- `patient_management`: Patient records, medical history, allergies
- `doctor_schedule`: Doctor appointments, shifts, consultations
- `prescriptions`: Electronic prescriptions and pharmacy integration
- `lab_management`: Lab tests, orders, and diagnostic reports

When a new module is added to this directory:
1. Update your Odoo Apps list: Go to **Apps** > **Update Apps List** (or run Odoo with `-u <module_name>`).
2. Search and click **Activate** on the module.
3. The Odoo MCP server will automatically detect and expose all new models and fields created by the module to your AI Copilot!
