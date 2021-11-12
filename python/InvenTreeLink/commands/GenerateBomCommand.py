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
            ao = apper.AppObjects()
            design = ao.product

            if not design:
                ao.ui.messageBox('No active design', 'Extract BOM')
                return

            root = design.rootComponent

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

                bom = functions.extract_bom()

                component_tree = functions.make_component_tree()
                
                element_synced = "<span style='color: green'> Synced </span>"
                element_not_synced = "<span style='color: red'> Not synced </span>"

                header = ''.join((
                    f"<h1>{root.name} </h1>"
                ))

                body = ''.join([
                    ''.join((
                        "<tr>"
                        f"<td>{item['IPN']} | {item['name']}</td>"
                        f"<td>{item['instances']}</td>"
                        f"<td>{element_synced if item['part'] else element_not_synced}</td>"
                        "</tr>" 
                    ))
                    for item in bom
                ])

                table_c = ''.join([
                    "<div class='overflow-auto'>",
                    "<table class='table table-sm table-striped table-hover'>",
                    "<thead>",
                    "<tr>",
                    "<th scope='col'> Name </th>",
                    "<th scope='col'> Count </th>",
                    "<th scope='col'> Synced </th>",
                    "</tr>",
                    f"</thead><tbody>{body}</tbody></table></div>",
                ])

                complete = ''.join((
                    header,
                    f"<p> {len(bom)} parts found in {datetime.now() - start}</p>"
                    f"{table_c}"
                    "<button onclick='onClickSyncAll()' class='btn btn-outline-secondary'> Sync All </button>" 
                    "<button onclick='onClickUploadBom()' class='btn btn-outline-secondary'> Upload BOM </button>"    
                ))

                palette.sendInfoToHTML(
                    config.DEF_SEND_BOM,
                    complete
                )

                palette.sendInfoToHTML(
                    'SendTree',
                    json.dumps(component_tree)
                )
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            raise _e
