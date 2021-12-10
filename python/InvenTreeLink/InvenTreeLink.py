import adsk.core
import traceback

import os

import threading

try:
    from .apper import apper
    from . import config
    from . import functions

    # Create our addin definition object
    my_addin = apper.FusionApp(config.app_name, config.company_name, False)
    my_addin.root_path = config.app_path

    from .commands.EditPartCommand import EditPartCommand
    from .commands.BOMOverviewCommand import BomOverviewPaletteShowCommand
    from .commands.GenerateBomCommand import GenerateBomCommand
    from .commands.ImportStlCommand import ImportStlCommand
    from .commands.ImportPartCommand import ImportPartCommand
    
    # Commands

    # Palette
    my_addin.add_command(
        'Show BOM overview',
        BomOverviewPaletteShowCommand,
        {
            'cmd_description': 'Show the BOM overview palette',
            'cmd_id': config.DEF_SHOW_PALETTE,
            'workspace': 'FusionSolidEnvironment',
            'toolbar_panel_id': config.ToolbarPanelID.INVENTREE_LINK,
            'cmd_resources': 'ShowPalette',
            'command_visible': True,
            'command_promoted': True,
            'palette_id': config.ITEM_PALETTE,
            'palette_name': 'InvenTreeLink BOM overview',
            'palette_html_file_url': os.path.join('commands', 'palette_html', 'palette.html'),
            'palette_use_new_browser': True,
            'palette_is_visible': True,
            'palette_show_close_button': True,
            'palette_is_resizable': True,
            'palette_width': 500,
            'palette_height': 600,
        }
    )

    # Commands that need the palette
    my_addin.add_command(
        'Load BOM for assembly',
        GenerateBomCommand,
        {
            'cmd_description': 'Load the BOM for the assembly in the current file',
            'cmd_id': config.DEF_SEND_BOM,
            'workspace': 'FusionSolidEnvironment',
            'toolbar_panel_id': config.ToolbarPanelID.INVENTREE_LINK,
            'cmd_resources': config.DEF_SEND_BOM,
            'command_visible': True,
            'command_promoted': False,
            'palette_id': config.ITEM_PALETTE,
        }
    )

    my_addin.add_command(
        'Edit Part',
        EditPartCommand,
        {
            'cmd_description': 'Show the InvenTree part-details for the selected part',
            'cmd_id': config.DEF_SEND_PART,
            'workspace': 'FusionSolidEnvironment',
            'toolbar_panel_id': config.ToolbarPanelID.PART,
            'cmd_resources': config.DEF_SEND_PART,
            'command_visible': True,
            'command_promoted': False,
        }
    )

    my_addin.add_command(
        'Import Part',
        ImportPartCommand,
        {
            'cmd_description': 'Import a Part as STL',
            'cmd_id': config.DEF_IMPORT_PART,
            'workspace': 'FusionSolidEnvironment',
            'toolbar_panel_id': config.ToolbarPanelID.PART,
            'cmd_resources': config.DEF_SEND_BOM,
            'command_visible': True,
            'command_promoted': False,
            'palette_id': config.ITEM_PALETTE,
        }
    )

    my_addin.add_command(
        'Export STEP',
        ImportStlCommand,
        {
            'cmd_description': 'Generates a STEP file and attaches it to a part',
            'cmd_id': config.DEF_SEND_STEP,
            'workspace': 'FusionSolidEnvironment',
            'toolbar_panel_id': config.ToolbarPanelID.PART,
            'cmd_resources': 'ShowPalette',
            'command_visible': True,
            'command_promoted': False,
            'palette_id': config.ITEM_PALETTE,
        }
    )

    app = adsk.core.Application.cast(adsk.core.Application.get())
    ui = app.userInterface

    functions.init_sentry()

    if functions.load_config(ui) is False:
        ui.messageBox("Unable to load config.", config.app_name)
    
    functions.init_Fusion360()

    # class MyDocumentActivatedHandler(adsk.core.DocumentEventHandler):
    #     def __init__(self):
    #         super().__init__()
    #     def notify(self, args):
    #         eventArgs = adsk.core.DocumentEventArgs.cast(args)

    #         # Code to react to the event.
    #         ui.messageBox('In MyDocumentActivatedHandler event handler.\ndocument: {}'.format(eventArgs.document.name))   
        
    # class MyDocumentSavedHandler(adsk.core.DocumentEventHandler):
    #     def __init__(self):
    #         super().__init__()

    #     def notify(self, args):
    #         eventArgs = adsk.core.DocumentEventArgs.cast(args)

    #         # Code to react to the event.
    #         ui.messageBox('In MyDocumentSavedHandler event handler.')   

    # onDocumentSaved = MyDocumentSavedHandler()
    # app.documentSaved.add(onDocumentSaved)
    
    # onDocumentActivated = MyDocumentActivatedHandler()
    # app.documentActivated.add(onDocumentActivated)

    # def correct_inventree_names_thread():
    #     # Recursively correct the names to inventree names
    #     def correct_inventree_names(component):
    #         part = functions.inventree_get_part(component.id)

    #         if part:           
    #             if component.name.lower() != part.name.lower():
    #                 print(f"Correcting name of '{component.name}' to '{part.name}'")
    #                 component.name = part.name
                    
    #             if component.partNumber.lower() != part.IPN.lower():
    #                 print(f"Correcting IPN of '{component.partNumber}' to '{part.IPN}'")
    #                 component.partNumber = part.IPN

    #         for occurrence in component.occurrences:
    #             if occurrence.component:
    #                 correct_inventree_names(occurrence.component)

    #     ao = apper.AppObjects()
    #     root = ao.product.rootComponent

    #     for occurrence in root.occurrences:
    #         if occurrence.component:
    #             correct_inventree_names(occurrence.component)  

    # t = threading.Thread(target=correct_inventree_names_thread)
    # t.start()

    print("InvenTreeLink started.")

except:  # noqa: E722
    app = adsk.core.Application.get()
    ui = app.userInterface
    if ui:
        ui.messageBox('Initialization Failed: {}'.format(traceback.format_exc()))

debug = True


def run(context):
    my_addin.run_app()


def stop(context):
    my_addin.stop_app()
