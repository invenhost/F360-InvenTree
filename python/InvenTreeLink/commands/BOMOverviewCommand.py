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
                root_part = inventree_get_part(root.id)

                if root_part == False:      
                    item_list = Part.list(inv_api(), IPN=root.partNumber)
                    if len(item_list) == 0:
                        result = propose_create_f360_part(ao, root, 3)

                        if result == adsk.core.DialogResults.DialogYes:
                            root_part = helpers.create_f360_part(root, functions.config_ref(config.CFG_PART_CATEGORY))               
                        elif result == adsk.core.DialogResults.DialogNo:
                            return 

                    elif len(item_list) == 1:
                        root_part = item_list[0]

                    elif len(item_list) > 1:
                        ao.ui.messageBox(f"More than one item found with IPN <b>{root.partNumber}. Please resolve this in InvenTree for now.", "Sync All")
                        return
                
                root_part.save(data={ 
                    'name': root.name,
                    'IPN': root.partNumber,
                    'description': root.description if root.description else 'None'
                })
                helpers.write_f360_parameters(root_part, root)  
                
                bom = functions.extract_bom()
                for item in bom:
                    part = item['part']

                    if part == False:
                        component = item['occurence'].component

                        item_list = Part.list(functions.inv_api(), IPN=component.partNumber)
                        if len(item_list) == 0:
                            result = propose_create_f360_part(ao, component, 4)                            
                            if result == adsk.core.DialogResults.DialogYes:
                                part = helpers.create_f360_part(component, functions.config_ref(config.CFG_PART_CATEGORY))                     
                            elif result == adsk.core.DialogResults.DialogNo:
                                continue                          
                            elif result == adsk.core.DialogResults.DialogCancel:
                                return 
                                
                        elif len(item_list) == 1:
                            # Just link it
                            part = item_list[0]

                        elif len(item_list) > 1:
                            ao.ui.messageBox(f"More than one item found with IPN <b>{component.partNumber}. Please resolve this in InvenTree for now.", "Sync All")
                            continue
                        
                        part.save(data={ 
                            'name': component.name,
                            'IPN': component.partNumber,
                            'description': component.description if component.description else 'None'
                        })
                        helpers.write_f360_parameters(part, component)  

                # Refresh this table                
                if palette:
                    command = helpers.get_cmd(ao, config.DEF_SEND_BOM)
                    command.execute()

            elif html_args.action == 'UploadBom':                
                root = ao.product.rootComponent
                root_part = functions.inventree_get_part(root.id)

                bom = functions.extract_bom()
                if False in [item['part'] for item in bom] or root_part is False:
                    ao.ui.messageBox("There's a Part not synced to InvenTree, unable to upload BOM.")
                    return

                if root_part.assembly is False:
                    root_part.save({
                        'assembly': True
                    })

                for item in bom:                    
                    BomItem.create(inv_api(), {
                        'part': root_part.pk,
                        'quantity': item['instances'],
                        'sub_part': item['part'].pk
                    })

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

def sync_all(ao, root: adsk.fusion.Component):
    from inventree.part import Part
    from inventree.part import BomItem

    root_part = inventree_get_part(root.id)

    if root_part == False:      
        item_list = Part.list(inv_api(), IPN=root.partNumber)
        if len(item_list) == 0:
            result = propose_create_f360_part(ao, root, 3)

            if result == adsk.core.DialogResults.DialogYes:
                root_part = helpers.create_f360_part(root, functions.config_ref(config.CFG_PART_CATEGORY))               
            elif result == adsk.core.DialogResults.DialogNo:
                return 

        elif len(item_list) == 1:
            root_part = item_list[0]

        elif len(item_list) > 1:
            ao.ui.messageBox(f"More than one item found with IPN <b>{root.partNumber}. Please resolve this in InvenTree for now.", "Sync All")
            return
    
    root_part.save(data={ 
        'name': root.name,
        'IPN': root.partNumber,
        'description': root.description if root.description else 'None'
    })
    helpers.write_f360_parameters(root_part, root)      

    for occurrence in root.occurrences:
        if occurrence.component:
            sync_all(occurrence.component)
