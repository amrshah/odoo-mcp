# VetCairn Complete Suite Installer

Install the **VetCairn Complete Suite Installer** application in Odoo Apps to
install the entire internal VetCairn suite at once.

Command-line installation:

```bash
python -m odoo -c odoo19.conf -d YOUR_DATABASE -i vet_installer --stop-after-init
```

The database must be backed up before installing into an existing environment.
External payment, messaging, laboratory, and portal integrations are not part of
this installer.
