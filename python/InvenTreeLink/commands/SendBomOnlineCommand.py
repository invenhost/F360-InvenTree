import adsk.core
import adsk.fusion
import adsk.cam

from ..apper import apper
from .. import config
from .. import functions


class SendBomOnlineCommand(apper.Fusion360CommandBase):
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
                inv_status = functions.inventree_get_part([a['id'] for a in config.BOM])
                for a in config.BOM:
                    a['status'] = inv_status[a['id']]

                body = ''.join(
                    ['<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (a['name'], a['instances'], a['status']) for a in config.BOM]
                )
                table = '<div class="overflow-auto"><table class="table table-sm table-striped table-hover"><thead><tr><th scope="col">Name</th><th scope="col">Count</th><th scope="col">Is InvenTree</th></tr></thead><tbody>{body}</tbody></table></div>'.format(body=body)

                palette.sendInfoToHTML(
                    config.DEF_SEND_BOM,
                    '{table}'.format(table=table)
                )
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            raise _e
