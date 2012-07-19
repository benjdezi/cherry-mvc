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
import cherrypy

DEV_DEBUG_PATTERN = "${dev_debug_info}"
DEFAULT_TEMPLATE_EXT = "html"
DEFAULT_REQ_CACHE_TTL = 24*3600

def test_action(f):
    ''' Define a test action, only accessible in dev environment '''
    def check_if_dev(*args, **kw):
        if Config.is_prod():
            controller = args[0]
            controller.send_error(404)
        else:
            return f(*args, **kw)
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

