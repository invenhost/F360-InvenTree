## Welcome to GitHub Pages

### Installation

1. Get a release (please do not try to use the `main` branch - there is no CI right now)
1. Unpack it
1. Place it into %AppData%\Autodesk\Autodesk Fusion 360\API\AddIns`
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
