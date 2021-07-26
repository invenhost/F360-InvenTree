## F360-InvenTree Addin-documentation

A BOM-Management-Addin for Fusion360 + InvenTree created by [Matthias Mair](https://mjmair.com) licensed under the [MIT license](https://github.com/matmair/F360-InvTree/blob/main/LICENSE).

{{site.data.alerts.note}}
This code is very much not finished and just a few hundred lines.
{{site.data.alerts.end}}

### Why
InvenTree is a great project for managing parts and BOMS and there is a fantastic plugin for KiCad to get data into it. But I use Fusion360 so here is a Addin for doing that.

### Base functionality: Linking

Each component in Fusion360 has a unique identifier - this identifier can be saved as a parameter to InvenTree. When using linked parts in Fusion360 the Addin can either read all identifiers and match them with InvenTree parameters or the parts primary-keys can be saved as a attribute within the components.

### Included tools

The Addin renders a palette which displays all components in the currently open file. The user can load in if the Fusion360 components are linked to a InvenTree part.
Components can also be added to InvenTree as parts or linked with parts.


### Installation

1. Get a release (please do not try to use the `main` branch - there is no CI right now)
1. Unpack it
1. Place it into `%AppData%\Autodesk\Autodesk Fusion 360\API\AddIns`
1. Enable it in the fusion360 Addin - panel

There is also a nice [guide by Autodesk](https://knowledge.autodesk.com/support/fusion-360/troubleshooting/caas/sfdcarticles/sfdcarticles/How-to-install-an-ADD-IN-and-Script-in-Fusion-360.html).

### Configuration

The Addin is configured using a file named `conf.ini` in the `InvenTree` directory.

```ini
[SERVER]
current = local

[local]
address = http://127.0.0.1:8000/
token = ee335d3eb22186token5e824e0ad4837ac874
category = plugin-test
part_id = Fusion360-ID
```

`adress` is the URL of the InvenTree instance that should be used  
`token` is a valid token to write information to InvenTree  
`category` is the name of the category new parts should be placed into  
`part_id` is the name of the Parameter that should be used to save the Fusion360 parts number  
