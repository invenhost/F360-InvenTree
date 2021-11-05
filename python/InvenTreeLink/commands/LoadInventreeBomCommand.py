import adsk.core
import adsk.fusion
import adsk.cam

from ..apper import apper
from .. import config
from .. import functions

# Loads the Bill of Materials that Inventree has of this Part.
class LoadInventreeBomCommand(apper.Fusion360CommandBase):
    def on_execute(self, command: adsk.core.Command, command_inputs: adsk.core.CommandInputs, args, input_values):
        try:
            # Get Reference to Palette
            ao = apper.AppObjects()
            palette = ao.ui.palettes.itemById(config.ITEM_PALETTE)

            # Send message to the HTML Page
            if palette:
                palette.sendInfoToHTML(
                    config.DEF_SEND_BOM,
                    '<br><br><br><div class="d-flex justify-content-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>'
                )

                # Work with it
                bom_parts = functions.inventree_get_part([item['id'] for item in config.BOM])
                for item in config.BOM:
                    part = bom_parts[item['id']]

                    if part is not False:
                        item['status'] = "<span style='color: green;'> Synced </span>"
                    else:
                        item['status'] = "<span style='color: red;'>Not synced</span>"

                body = ''.join(
                    [
                        f"<tr> <td> {item['name']} </td> <td> {item['instances']} </td> <td> {item['status']} </td> </tr>"
                        for item in config.BOM
                    ]
                )
                table = '<div class="overflow-auto"><table class="table table-sm table-striped table-hover"><thead><tr><th scope="col">Name</th><th scope="col">Count</th><th scope="col">Status</th></tr></thead><tbody>{body}</tbody></table></div>'.format(body=body)

                palette.sendInfoToHTML(
                    config.DEF_SEND_BOM,
                    '{table}'.format(table=table)
                )
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            raise _e
