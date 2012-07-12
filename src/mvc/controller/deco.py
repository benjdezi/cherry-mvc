'''
Created on Jul 12, 2012

Decorators for controller actions

@requires: CherryPy (http://docs.cherrypy.org/stable/intro/install.html)
@requires: py-utils (https://github.com/benjdezi/Python-Utils)
@author: Benjamin Dezile
'''

from pyutils.lib.cache import Cache
from pyutils.utils.config import Config
from pyutils.utils.logging import Logger
from mvc.server import session
from mvc.controller.utils import render_template
from cStringIO import StringIO
from time import time
import cherrypy

DEV_DEBUG_PATTERN = "${dev_debug_info}"
DEFAULT_TEMPLATE_EXT = "html"
DEFAULT_REQ_CACHE_TTL = 24*3600

def test_action(f):
    ''' Define a test action, only accessible in dev environment '''
    def check_if_dev(*args, **kw):
        if Config.is_dev():
            return f(*args, **kw)
        else:
            raise Exception("No accessible")
    return check_if_dev

def cached(f):
    ''' Cache the output of the wrapped method based on input parameters '''
    def exec_cached_method(*args, **kw):
        
        no_cache = kw.get("nocache", False)
        out = None
        
        if kw.has_key('nocache'):
            del kw['nocache']
        
        if not no_cache:
                
            controller = args[0]
            action_name = f.func_name
            
            cache_key = Cache.make_ns_key(Cache.NS_REQUEST, controller.name, action_name, kw)        
            out = Cache.get(cache_key, no_eval=True)
            
        if not out:
            out = f(*args, **kw)
            if not no_cache and out:
                Cache.put(cache_key, out, DEFAULT_REQ_CACHE_TTL)
                Logger.debug("Caching request for %s" % cache_key)
        else:
            Logger.debug("Read request from cache for %s" % cache_key)
            
        return out
    exec_cached_method.__name__ = f.__name__
    return exec_cached_method
    
def async(f):
    ''' Define an action as asynchronous '''
    f.is_async = True
    return f
        
def web_page(f):
    ''' Wrap the result of the decorated method into a web page '''
    def make_web_page(*args, **kw):
        return _generate_web_page(args[0], f, args, kw)
    return make_web_page

def web_page_blank(f):
    ''' Wrap the result of the decorated method into a blank web page '''
    def make_web_page(*args, **kw):
        return _generate_web_page(args[0], f, args, kw, True, False, False)
    return make_web_page

def authenticated(f):
    ''' Ensure that there is an authenticated user in session '''
    def check_authentication(*kargs, **kwargs):
        session.assert_user_in_session()
        return f(*kargs, **kwargs)
    return check_authentication

def admin_only(f):
    ''' Ensure that the wrap method can only be accessed by admin users '''
    def check_admin_rights(*kargs, **kwrags):
        user = session.get_user()
        if user and user.is_admin():
            return f(*kargs, **kwrags)
        else:
            raise cherrypy.HTTPError(401, "Page outside of scope")
    return check_admin_rights


##  HELPERS  ####################################

def _render_dev_debug(start_time):
    ''' Render debug info '''
    dt = int((time() - start_time) * 1000.0)
    buf = StringIO()
    buf.write("<div class='dev_debug'>")
    buf.write("<span>Time: %s ms</span>" % dt) 
    buf.write("<a class='hide_dev'>x</a>")
    buf.write("</div>")
    buf.write("<script type='text/javascript'>")
    buf.write("$(document).ready(function(){ $('.dev_debug > a.hide_dev').click(function(){ $('.dev_debug').hide(); }); });")
    buf.write("</script>")
    s = buf.getvalue()
    buf.close()
    return s

def _generate_web_page(inst, f, f_args, f_kw, head=True, header=True, footer=True):
    ''' Generate the HMTL code that wraps around the response from the given method '''
    ctx = { 'action': f.func_name, 'controller': inst.name }
    start_time = time()
    buf = StringIO()
    buf.write("<!DOCTYPE html PUBLIC \"-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd\">\n")
    buf.write("<html>\n\n")
    buf.write("<head>\n")
    if head is True:
        buf.write(render_template("sub/head", ctx))
    buf.write("\n</head>\n\n")
    buf.write("<body>\n")
    buf.write("%s\n" % DEV_DEBUG_PATTERN if Config.is_dev() else "")
    if header is True:
        buf.write(render_template("sub/header", ctx))
    buf.write("\n")
    buf.write(f(*f_args, **f_kw))
    buf.write("\n")
    if footer is True:
        buf.write(render_template("sub/footer", ctx))
    buf.write("\n</body>\n\n")
    buf.write("</html>\n")
    page_data = buf.getvalue()
    buf.close()
    if Config.is_dev():
        return page_data.replace(DEV_DEBUG_PATTERN, _render_dev_debug(start_time))
    return page_data
