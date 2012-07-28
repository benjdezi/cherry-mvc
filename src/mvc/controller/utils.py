'''
Created on Jul 12, 2012

Controller helpers

@requires: Mako (pip install Mako)
@requires: py-utils (https://github.com/benjdezi/Python-Utils)
@author: Benjamin Dezile
'''

from mako.runtime import Context
from mako.lookup import TemplateLookup
from mako import exceptions
from pyutils.utils.config import Config
from pyutils.utils import helpers
from mvc.server import session
from cStringIO import StringIO
import urllib
import json
import os


FILE_CHECKS = Config.get("templates", "file_checks")
TEMPLATE_CACHE_DIR = Config.get("templates", "cache_dir")

DEFAULT_TEMPLATE_EXT = Config.get("templates", "default_ext")
if not DEFAULT_TEMPLATE_EXT:
    DEFAULT_TEMPLATE_EXT = "html"


def render_template(path, params=dict()):
    ''' Render a template for the given parameters 
        path:      Template absolute path
        params:    Rendering parameters
    '''
    
    path_parts = path.split(os.path.sep)
    full_path = os.path.sep.join(path_parts[:-1])
    file_name = os.path.sep + path_parts[-1]
    if file_name.find(".") < 0:
        file_name += "." + DEFAULT_TEMPLATE_EXT
    
    lookup = TemplateLookup(directories=[full_path], filesystem_checks=FILE_CHECKS, module_directory=TEMPLATE_CACHE_DIR)
    template = lookup.get_template(file_name)
    
    params['include_template'] = render_template
    params['config'] = Config
    params['session'] = session
    params['helpers'] = helpers
    
    buf = StringIO()
    ctx = Context(buf, **params)
    try: 
        template.render_context(ctx)
        return buf.getvalue()
    except:
        return exceptions.html_error_template().render()
    finally:
        if buf: buf.close()

def format_http_args(args):
    ''' Format the given HTTP argument to proper python types '''
    formatted_args = dict()
    for key in args:
        value = args[key]
        p = key.find("[")
        if p > 0 and key[p+1] is "]":
            # List (already handled by cherry)
            key = key[:p]
            formatted_args[key] = value if (type(value) is list) else [value]
        elif p > 0:
            # Dictionary
            q = key.find("]", p)
            if len(key) > q+1 and key[q+1] is "[":
                # Multi level
                levels = key[p+1:-1].split("][")
                base_key = key[:p]
                if not formatted_args.has_key(base_key):
                    formatted_args[base_key] = dict()
                cur_dict = formatted_args[base_key]
                for level_key in levels[:-1]:
                    if not cur_dict.has_key(level_key):
                        cur_dict[level_key] = dict()
                    cur_dict = cur_dict[level_key] 
                cur_dict[levels[-1]] = urllib.unquote(value)
            else:
                # Single level
                base_key = key[:p]
                if not formatted_args.has_key(base_key):
                    formatted_args[base_key] = dict()
                formatted_args[base_key][key[p+1:-1]] = urllib.unquote(value)
        else:
            # Single value
            formatted_args[key] = value
    return formatted_args 

def format_async_response(resp_data=dict(), success=True, ex=None):
    ''' Wrap the given data into a standard async response '''
    resp = dict()
    resp['success'] = success
    if resp_data is not None:
        resp['data'] = resp_data
    if not success and ex:
        resp['error'] = str(ex)
    return json.dumps(resp)
