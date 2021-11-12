import adsk.core
import adsk.fusion
import adsk.cam

import json

from ..apper import apper
from .. import config
from .. import helpers
from .. import functions
        
from ..functions import inv_api, inventree_get_part

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
        
        from inventree.part import Part
        from inventree.part import BomItem

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
                
                root = ao.product.rootComponent
                sync_all(ao, root)

                # Refresh this table                
                if palette:
                    command = helpers.get_cmd(ao, config.DEF_SEND_BOM)
                    command.execute()

            # TODO investigate ghost answers
            # else:
            #     raise NotImplementedError('unknown message received from HTML')
        except Exception as _e:
            config.app_tracking.capture_exception(_e)
            helpers.error()

    # Handle any extra cleanup when user closes palette here
    def on_palette_close(self):
        pass

def propose_create_f360_part(ao, component: adsk.fusion.Component, buttons):
    physicalProperties = component.physicalProperties

    fusion_360_data = (
        f"Part Number: <b>{component.partNumber}</b><br />"
        f"Name: <b>{component.name}</b><br />"
        f"Description: <b>{component.description}</b><br /><br />"

        f"ID: {component.id}<br />"
        f"Area: {physicalProperties.area}cm2<br />"
        f"Volume: {physicalProperties.volume}cm3<br />"
        f"Mass: {physicalProperties.mass}kg<br />"
        f"Density: {physicalProperties.density}g/cm3<br />"
    )

    if component.material and component.material.name:
        fusion_360_data += f"Material: {component.material.name}<br />"

    axis = ['x', 'y', 'z']
    bb_min = {a: getattr(component.boundingBox.minPoint, a) for a in axis}
    bb_max = {a: getattr(component.boundingBox.maxPoint, a) for a in axis}
    bb = {a: bb_max[a] - bb_min[a] for a in axis}

    fusion_360_data += (
        f"Dimensions: {bb['x']}cm x {bb['y']}cm x {bb['z']}cm<br />"
    )

    text = (
        f"Part <b>{component.partNumber} | {component.name}</b> is not recognized by Inventree.<br />"
        "<b>Do you want to create a Part with the values provided by Fusion360?</b><br /><br />"
        f"<i>{fusion_360_data}</i>"
    )

    return ao.ui.messageBox(text, "Sync All", buttons, 1)

def sync_all(ao, root: adsk.fusion.Component, updated={}):
    from inventree.part import Part
    from inventree.part import BomItem

    root_part = inventree_get_part(root.id)

    if root_part == False:      
        item_list = Part.list(inv_api(), IPN=root.partNumber)
        if len(item_list) == 0:
            root_part = helpers.create_f360_part(root, functions.config_ref(config.CFG_PART_CATEGORY))

        elif len(item_list) == 1:
            root_part = item_list[0]

        elif len(item_list) > 1:
            ao.ui.messageBox((
                f"Part <i>{root.name}</i> does not have a unique IPN <b>{root.partNumber}</b>.<br />"
                "<b>Please resolve this in InvenTree for now.</b>"
            ), "Sync All")
            return
    
    # Delete previous bom
    for item in root_part.getBomItems():
        item.delete() 

    root_part.save(data={ 
        'name': root.name,
        'IPN': root.partNumber,
        'description': root.description if root.description else 'None',
        # If the part has more than one occurences, it's probably an assembly.
        # However, if you marked it Purchasable in InvenTree, it will not be an assembly.
        'assembly': len(root.occurrences) > 0 and not root_part.purchaseable
    })
    helpers.write_f360_parameters(root_part, root)      
       
    if root_part.assembly:
        instance_count = {}
        for occurrence in root.occurrences:
            if occurrence.component:
                if str(occurrence.component.id) in instance_count:
                    instance_count[occurrence.component.id] += 1
                else:
                    instance_count[occurrence.component.id] = 1

                if not str(occurrence.component.id) in updated:
                    sync_all(ao, occurrence.component, updated)
                    updated[str(occurrence.component.id)] = True     

        for id in instance_count:
            part = inventree_get_part(id)    

            if part is not False:
                BomItem.create(inv_api(), {
                    'part': root_part.pk,
                    'quantity': instance_count[id],
                    'sub_part': part.pk
                })
            else:
                ao.ui.messageBox(f"Make sure you don't have duplicate IPN + names in child drawings of {root_part.name}!", "")
