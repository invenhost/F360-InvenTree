import adsk.core
import adsk.fusion
import adsk.cam

import json
from datetime import datetime

from ..apper import apper
from .. import config
from .. import functions

import threading

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
            def create_bom_thread():
                loading_html = (
                    '<br><br><br>'

                    '<div class="d-flex justify-content-center">'
                        '<div class="spinner-border" role="status">'
                            '<span class="visually-hidden">Loading...</span>'
                        '</div>'
                    '</div>'                
            
                    '<div class="d-flex justify-content-center">'
                        '<p> Retrieving BOM...</p>'
                    '</div>'
                )

                palette.sendInfoToHTML(
                    config.DEF_GENERATE_BOM,
                    loading_html
                )

                start = datetime.now()
                bom = functions.extract_bom()
                
                element_synced = "<span style='color: green'> Synced </span>"
                element_not_synced = "<span style='color: red'> Not synced </span>"

                header_html = (
                    f"<h1>{root.name} </h1>"
                )

                body = ''.join([
                    (
                        "<tr>"
                            f"<td>{item['IPN']} | {item['name']}</td>"
                            f"<td>{item['instances']}</td>"
                            f"<td>{element_synced if item['part'] else element_not_synced}</td>"
                        "</tr>" 
                    )
                    for item in bom
                ])

                table_html = (
                    "<div class='overflow-auto'>"
                        "<table class='table table-sm table-striped table-hover'>"
                            "<thead>"
                                "<tr>"
                                "<th scope='col'> Name </th>"
                                "<th scope='col'> Count </th>"
                                "<th scope='col'> Synced </th>"
                                "</tr>"
                            "</thead>"
                            "<tbody>"
                                    f"{body}"
                            "</tbody>"
                        "</table>"
                    "</div>"
                )

                complete_html = (
                    f"{header_html}"
                    f"<p> {len(bom)} parts found in {datetime.now() - start}</p>"
                    f"{table_html}"
                )
                
                palette.sendInfoToHTML(
                    config.DEF_GENERATE_BOM,
                    json.dumps(complete_html)
                )

            #create_bom_thread()
            t = threading.Thread(target=create_bom_thread, args=())
            t.start()
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            raise _e
