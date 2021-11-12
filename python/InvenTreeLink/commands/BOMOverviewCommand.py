import adsk.core
import adsk.fusion
import adsk.cam

import json

from ..apper import apper
from .. import config
from .. import helpers
from .. import functions


# Class for a Fusion 360 Palette Command
class BomOverviewPaletteShowCommand(apper.PaletteCommandBase):

    # Run when user executes command in UI, useful for handling extra tasks on palette like docking
    def on_palette_execute(self, palette: adsk.core.Palette):

        # Dock the palette to the right side of Fusion window.
        if palette.dockingState == adsk.core.PaletteDockingStates.PaletteDockStateFloating:
            palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight

    # Run when ever a fusion event is fired from the corresponding web page
    def on_html_event(self, html_args: adsk.core.HTMLEventArgs):
        data = json.loads(html_args.data)

        try:
            ao = apper.AppObjects()
            palette = ao.ui.palettes.itemById(config.ITEM_PALETTE)

            if html_args.action == 'getBom':
                if palette:
                    command = helpers.get_cmd(ao, config.DEF_SEND_BOM)
                    command.execute()

            elif html_args.action == 'getBomOnline':
                if palette:
                    helpers.get_cmd(ao, config.DEF_SEND_ONLINE_STATE).execute()

            elif html_args.action == 'showPart':
                selections = ao.ui.activeSelections
                selections.clear()

                cmp = ao.activeProduct.allComponents.itemById(data['id'])
                token = cmp.entityToken
                entitiesByToken = ao.product.findEntityByToken(token)
                selections.add(entitiesByToken)  # TODO selection not working
                helpers.get_cmd(ao, config.DEF_SEND_PART).execute()

            elif html_args.action == 'SyncAll':
                from inventree.part import Part
                ao.ui.messageBox("Sync All")
                
                bom = functions.extract_bom()
                for item in bom:
                    part = item['part'];

                    if part == False:
                        occ = item['occurence']

                        item_list = Part.list(functions.inv_api(), IPN=occ.component.partNumber)
                        if len(item_list) == 0:
                            fusion_360_data = (
                                f"ID: {occ.component.id}<br />"
                                f"Area: {occ.component.physicalProperties.area}cm2<br />"
                                f"Volume: {occ.physicalProperties.volume}cm3<br />"
                                f"Mass: {occ.physicalProperties.mass}kg<br />"
                                f"Density: {occ.physicalProperties.density}g/cm3<br />"
                            )

                            if occ.component.material and occ.component.material.name:
                                fusion_360_data += f"Material: {occ.component.material.name}\n"

                            text = (
                                f"Part <b>{occ.component.partNumber} | {occ.component.name}</b> is not recognized by Inventree.<br />"
                                "<b>Do you want to create a Part with the values provided by Fusion360?</b><br /><br />"
                                f"<i>{fusion_360_data}</i>"
                            )
                            
                            result = ao.ui.messageBox(text, "Sync All", 4, 1)
                            if result == adsk.core.DialogResults.DialogYes:
                                item['part'] = helpers.create_f360_part(occ, functions.config_ref(config.CFG_PART_CATEGORY))                     
                            elif result == adsk.core.DialogResults.DialogNo:
                                continue                          
                            elif result == adsk.core.DialogResults.DialogCancel:
                                return 
                        elif len(item_list) == 1:
                            # Just link it
                            helpers.write_f360_parameters(part, occ)

            elif html_args.action == 'UploadBom':
                ao.ui.messageBox("Uploading bom")



            # TODO investigate ghost answers
            # else:
            #     raise NotImplementedError('unknown message received from HTML')
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            helpers.error()

    # Handle any extra cleanup when user closes palette here
    def on_palette_close(self):
        pass
