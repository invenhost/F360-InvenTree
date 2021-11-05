import adsk.core
import adsk.fusion
import adsk.cam

import json
from datetime import datetime

from ..apper import apper
from .. import config
from .. import functions

# Loads the Bill of Materials from the current Fusion360 design.
class GenerateBomCommand(apper.Fusion360CommandBase):
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

                start = datetime.now()
                config.BOM = functions.extract_bom()
                config.BOM_HIR = functions.make_component_tree()
                body = ''.join(['<tr><td>%s</td><td>%s</td></tr>' % (a['name'], a['instances']) for a in config.BOM])
                table_c = '<div class="overflow-auto"><table class="table table-sm table-striped table-hover"><thead><tr><th scope="col">Name</th><th scope="col">Count</th></tr></thead><tbody>{body}</tbody></table></div>'.format(body=body)

                palette.sendInfoToHTML(
                    config.DEF_SEND_BOM,
                    '<p>{count} parts found in {time}</p>{table}'.format(
                        count=len(config.BOM),
                        table=table_c,
                        time=datetime.now() - start
                    )
                )
                palette.sendInfoToHTML(
                    'SendTree',
                    json.dumps(config.BOM_HIR)
                )
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            raise _e
