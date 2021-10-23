
import unicodedata
import re
import traceback

from .apper import apper
from . import config


# https://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename
def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


def error(typ_str=None):
    """ shows message box when error raised """
    # generate error message
    if typ_str == 'cmd':
        ret_msg = 'Command executed failed: {}'.format(traceback.format_exc())
    else:
        ret_msg = 'Failed:\n{}'.format(traceback.format_exc())

    # show message
    ao = apper.AppObjects()
    if ao.ui:
        ao.ui.messageBox(ret_msg)
    else:
        print(ret_msg)


def get_cmd(ao, key):
    ref_name = f'{config.company_name}_{config.app_name}_{key}'
    return ao.ui.commandDefinitions.itemById(ref_name)
