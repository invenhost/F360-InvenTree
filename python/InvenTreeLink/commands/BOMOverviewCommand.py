import adsk.core
import adsk.fusion
import adsk.cam

import json

from ..apper import apper
from .. import config
from .. import helpers
from .. import functions
        
from ..functions import inv_api, inventree_get_part

import threading
import typing

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

                # sync_all_thread(ao, root)

                t = threading.Thread(target=sync_all_thread, args=(ao, root))
                t.start()

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
  

@apper.lib_import(config.lib_path)
def sync_all_thread(ao, root: adsk.fusion.Component):
    palette = ao.ui.palettes.itemById(config.ITEM_PALETTE)

    log_html = []
    def log(message: str, color: str = "black"):
        log_html.append(f'<span style="color: {color};">{message}</span>')

        palette.sendInfoToHTML(
            config.DEF_SYNC_LOG,
            '<br />'.join(log_html)
        )  
        
    palette.sendInfoToHTML(
        config.DEF_SEND_BOM,
        (
            '<div id="loading">'
                '<br><br><br>'
                '<div class="d-flex justify-content-center">'
                    '<div class="spinner-border" role="status"> </div>'
                    '</div>'

                    '<div id="ignore_warnings" style="display: none;">'         
                        '<div class="d-flex justify-content-center">'   
                        '<button onclick="" class="btn btn-outline-secondary"> Ignore warnings and Sync </button>'
                    '</div>'
                '</div>'
            
                '<div class="d-flex justify-content-center">'
                    '<b> Syncing <span id="status">...</span> </b>'
                '</div>'

                '<br />'
            '</div>'

            '<div class="d-flex justify-content-center">'
                '<div id="sync_log"> </div>'
            '</div'
        )
    )  

    if sync_all(ao, root, log) is True:
        ao.ui.messageBox('<br />'.join(log_html), "Synchronization")
    
    command = helpers.get_cmd(ao, config.DEF_SEND_BOM)
    command.execute()

COLOR_WARNING = "rgb(255,145,0)"
    
@apper.lib_import(config.lib_path)
def sync_all(ao, root: adsk.fusion.Component, log, visited={}, warning_raised = False):
    from inventree.part import Part
    from inventree.part import BomItem
    
    palette = ao.ui.palettes.itemById(config.ITEM_PALETTE)
    palette.sendInfoToHTML(
        "exec",
        f"document.getElementById('status').innerHTML = '{root.name}';"
    )  

    if root.name.lower() == root.partNumber.lower():
        log(f"Warning: {root.name}'s name is the same as it's part number!", COLOR_WARNING)
        warning_raised = True

    root_part = inventree_get_part(root.id)

    if root_part == False:      
        item_list = Part.list(inv_api(), IPN=root.partNumber)
        if len(item_list) == 0:
            root_part = helpers.create_f360_part(root, functions.config_ref(config.CFG_PART_CATEGORY))

        elif len(item_list) == 1:
            root_part = item_list[0]

        elif len(item_list) > 1:
            log((
                f"Part <i>{root.name}</i> does not have a unique (IPN = <b>'{root.partNumber}'</b>).<br />"
                "<b>Please resolve this in InvenTree for now.</b>"
            ), "red")
            warning_raised = True
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
        instance_name = {}
        instance_count = {}
        for occurrence in root.occurrences:
            if occurrence.component:
                if str(occurrence.component.id) in instance_count:
                    instance_count[occurrence.component.id] += 1
                else:
                    instance_count[occurrence.component.id] = 1
                    instance_name[occurrence.component.id] = occurrence.component.name

                if not str(occurrence.component.id) in visited:
                    sync_all(ao, occurrence.component, log, visited, warning_raised)
                    visited[str(occurrence.component.id)] = True     

        for id in instance_count:
            part = inventree_get_part(id)    

            if part is not False:
                BomItem.create(inv_api(), {
                    'part': root_part.pk,
                    'quantity': instance_count[id],
                    'sub_part': part.pk
                })
            else:
                log(f"Unable to get part for {instance_name[id]}")                
                warning_raised = True

    return warning_raised
