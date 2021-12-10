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
import sys

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
    print("Starting sync_all thread.")

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
                '</div>'
            
                '<div class="d-flex justify-content-center">'
                    '<p> Syncing <i><b><span id="status"></span></b></i>...</p>'
                '</div>'

                '<br />'
            '</div>'

            '<div class="d-flex justify-content-center">'
                '<div id="sync_log"> </div>'
            '</div'
        )
    )  

    visited = dict()
    sync_all(ao, root, log, None, visited, False)
    
    command = helpers.get_cmd(ao, config.DEF_SEND_BOM)
    command.execute()

    visited.clear()

    print("Stopping thread...")
    sys.exit()

COLOR_WARNING = "rgb(255,145,0)"
    
@apper.lib_import(config.lib_path)
def sync_all(ao, root: adsk.fusion.Component, log, parent = None, visited={}, warning_raised = False):
    from inventree.part import Part
    from inventree.part import BomItem
    
    palette = ao.ui.palettes.itemById(config.ITEM_PALETTE)
    palette.sendInfoToHTML(
        "exec",
        f"document.getElementById('status').innerHTML = '{root.name}';"
    )  

    if root.name.lower() == root.partNumber.lower():
        # The name is the same as the part number, remove the part number.
        root.partNumber = ""


    parent_info = f" in {parent.name}" if parent else ''
    #print(f"Updating {root.name}{parent_info}...")

    root_part = inventree_get_part(root.id)
    if root_part == False:
        # The part is not found using the fusion 360 ID.
        print(f"Unable to find {root.name} by Fusion 360 ID {root.id}.")

        if not root.partNumber or root.partNumber.startswith("Component"):
            try:                
                # If the partnumber is set by Fusion360, remove it for InvenTree
                root.partNumber = ""
            except:
                pass
            # The part does not have an IPN set, however this is no problem because it will be found
            # using the Fusion 360 ID.
            root_part = helpers.create_f360_part(root, functions.config_ref(config.CFG_PART_CATEGORY))
            print(f"{root.name} does not have it's IPN set, so created a new part.")

            log((
                f"<i><b>{root.name}</b></i>{parent_info} does not have a IPN set"
            ), "warn")
        else:
            # The part number is not empty, so search InvenTree for an existing part.
            item_list = Part.list(inv_api(), IPN=root.partNumber, has_ipn=True)

            if len(item_list) == 0:              
                # If the partnumber is not recognized by InvenTree, remove it for Fusion360
                root.partNumber = ""

                print(f"Item {root.name}{parent_info} is not matched by part number, but will be created with an empty IPN.")

                # There are no matches with this IPN, create the part.
                root_part = helpers.create_f360_part(root, functions.config_ref(config.CFG_PART_CATEGORY))
            elif len(item_list) == 1:
                #print(f"Item {root.name} is singly matched by part number.")
                # There's a single match by IPN, it must be the part we want.
                root_part = item_list[0]
            elif len(item_list) > 1:
                print(f"Item {root.name}{parent_info} is not matched by Fusion360 ID, but found {len(item_list)} items matching IPN {root.partNumber}")

                log((
                    f"Skipping part <i><b>{root.name}</b></i>{parent_info} because it does not have a unique IPN. (IPN = <b>'{root.partNumber}'</b>)"
                ), "red")

                return

    # If there's an inventree name, it will be copied and set.
    # If the part was created right before this, it was created with the 
    # part name of Fusion360, so this would have no side effect.
    new_name = root_part.name
    new_IPN = root_part.IPN

    # Exception is thrown when trying to edit root component name.
    try:
        root.name = new_name
    except:
        pass
    
    root.partNumber = new_IPN
    
    if not root_part.assembly:
        # Delete previous bom
        for item in root_part.getBomItems():
            item.delete() 

    #print(f"Before save: {new_name} was an assembly: {root_part.assembly} with {len(root.occurrences)} occs")

    root_part.save(data={ 
        'name': new_name,
        'IPN': new_IPN,
        'description': root.description if root.description else f'Fusion360 Name: {root.name}',
    })
    helpers.write_f360_parameters(root_part, root)      
    
    #print(f"After save: {new_name} is an assembly: {root_part.assembly} with {len(root.occurrences)} occs")
       
    if root_part.assembly:
        instance_name = {}
        instance_count = {}
        for occurrence in root.occurrences:
            if occurrence.component:
                if str(occurrence.component.id) in instance_count:
                    instance_count[str(occurrence.component.id)] += 1
                else:
                    instance_count[str(occurrence.component.id)] = 1
                    instance_name[str(occurrence.component.id)] = occurrence.component.name

                if str(occurrence.component.id) in visited:
                    #print(f"Skipping {occurrence.component.name} because it's already visited.") 
                    noop = True
                else:
                    sync_all(ao, occurrence.component, log, root, visited, warning_raised)
                    visited[str(occurrence.component.id)] = True    


        palette.sendInfoToHTML(
            "exec",
            f"document.getElementById('status').innerHTML = '{root.name}'s Bill of Materials';"
        )  
        parts = inventree_get_part([id for id in instance_count])
        print(f"Creating Bill of Materials for {new_name}... ")
        for id in instance_count:
            part = parts[id]

            if part is not False:
                BomItem.create(inv_api(), {
                    'part': root_part.pk,
                    'quantity': instance_count[id],
                    'sub_part': part.pk
                })
            else:
                log(f"Unable to get part for {instance_name[id]}")                
                warning_raised = True

        print(f"Done creating Bill of Materials for {new_name}.")
        
    #print(f"Updated part {root.name} ({root.id})")

    return warning_raised
