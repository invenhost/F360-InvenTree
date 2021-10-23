import adsk.core
import adsk.fusion
import adsk.cam

import json

from ..apper import apper
from .. import config
from .. import helpers


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

            # TODO investigate ghost answers
            # else:
            #     raise NotImplementedError('unknown message received from HTML')
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            helpers.error()

    # Handle any extra cleanup when user closes palette here
    def on_palette_close(self):
        pass
