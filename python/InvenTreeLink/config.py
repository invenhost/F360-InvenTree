import os.path


app_name = 'InvenTreeLink'
company_name = "mjmair"
app_tracking = None

# ***Ignore Below this line unless you are sure***
lib_dir = 'lib'
app_path = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(app_path, lib_dir, '')


# Magic numbers
ITEM_PALETTE = 'InvenTreePalette'

DEF_SHOW_PALETTE = "ShowPalette"
DEF_SEND_BOM = "SendBom"
DEF_SEND_ONLINE_STATE = "SendOnlineState"
DEF_SEND_PART = "SendPart"
DEF_SEND_STEP = "SendStep"
DEF_IMPORT_PART = "ImportPart"

CFG_ADDRESS = 'address'
CFG_TOKEN = 'token'
CFG_PART_CATEGORY = 'part_category'

# globals for reference
INV_API = None  # API-connection
CONFIG = {}  # Config section
REF_CACHE = {}  # saves refs for reduced loading

class ToolbarPanelID:
    COMMANDS = "Commands"
    INVENTREE_LINK = "Inventree Link"
    PART = "Part"