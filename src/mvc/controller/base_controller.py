'''
Created on Feb 24, 2012

@requires: CherryPy (http://docs.cherrypy.org/stable/intro/install.html)
@requires: py-utils (https://github.com/benjdezi/Python-Utils)
@author: Benjamin Dezile
'''

from pyutils.utils.logging import Logger
from pyutils.utils.config import Config
from mvc.controller.utils import format_http_args, render_template
from mvc.server import session
from urllib import urlencode
from time import time
import cherrypy
import inspect
import json


##  HELPERS  #################################

def _action_call_wrapper(f):
    ''' Monitor controller calls and performs some pre and post processing '''
    def wrapper(*kargs, **kwargs):
        
        inst = f.im_self
        name = f.__name__
        is_render_view = (name == "renderView")
        is_async = (hasattr(f, 'is_async') and f.is_async is True)
        is_action = (is_render_view or is_async)
        
        # Session recovery
        try:
            session.recover()
        except Exception, e:
            Logger.error("Could not recover session", e)  
        
        # Format arguments
        if is_action:
            formatted_kargs = format_http_args(kwargs)
        else:
            formatted_kargs = kwargs
        
        # Execute method
        start_time = time()
        if is_action:
            inst._before_action(name, **formatted_kargs)
            if is_async:
                res = _process_async_call(f, formatted_kargs)
            else:
                res = f(*kargs, **formatted_kargs)
            inst._after_action(name, **formatted_kargs)
        else:
            res = f(*kargs, **formatted_kargs)
        dt = round((time() - start_time) * 1000, 2)
        
        if is_render_view:
            Logger.debug("Rendered view %s in %s ms" % (kargs[0], dt))
        elif is_async:
            Logger.debug("Executed async call to %s in %s ms" % (name, dt))
        
        return res
    ret_f = wrapper
    ret_f.exposed = True
    return ret_f     

def _process_async_call(f, args):
    ''' Process an asynchronous action call and automatically format the response '''
    resp = { "success": True }
    try:
        res = f(**args)
        resp['data'] = res if res is not None else {}
    except cherrypy.HTTPError, e:
        raise e
    except Exception, e:
        Logger.error("Error while processing call to %s" % f.__name__, e)
        resp['success'] = False
        resp['error'] = str(e)
    json_resp = json.dumps(resp)
    if Config.is_dev():
        Logger.debug("Async response to %s: %s" % (f.__name__, json_resp))
    return json_resp


##  CONTROLLER  #################################

class BaseController(object):
    ''' Base controller
    Abstract base for all controllers.
    Contains all sorts of helpers and structures that may be needed in controllers.
    '''
    
    def __init__(self, name, path):
        self.name = name
        self.path = path
        # Automatically add call monitoring to instance methods
        # except one starting with _ (considered internal)
        for x in inspect.getmembers(self, (inspect.ismethod)):
            if not x[0].startswith('_'):
                attr = getattr(self, x[0])
                setattr(self, x[0], _action_call_wrapper(attr))
        
    def _before_action(self, action_name, **action_args):
        ''' Called right before an action is executed '''
        pass
    
    def _after_action(self, action_name, **action_args):
        ''' Called right after an action is executed '''
        pass
        
    def getName(self):
        ''' Return the controller's name '''
        return self.name
        
    @classmethod
    def renderView(cls, view_path, params=dict()):
        ''' Render a view with the given parameters '''
        return render_template(view_path, params)
    
    @classmethod
    def sendHTTPError(cls, status=500, msg="Server error"):
        ''' Return an error for the current request '''
        Logger.error("HTTP %s%s" % (status, (": " + msg if msg else "")))
        raise cherrypy.HTTPError(status, msg)
    
    @classmethod
    def _makeURL(cls, path, params=None):
        ''' Build a full url out of a path and parameters '''
        qs = urlencode(params) if params else ""
        path = path.strip("/")
        return ("/" + path + "/" if path else "/") + ("?" + qs if qs else "")
    
    @classmethod
    def forward(cls, controller, action=None, params=None):
        ''' Internally redirect the current request to the given action '''
        path = "/".join([controller, action]) if action else controller
        url = BaseController._makeURL(path, params)
        Logger.debug("Forwarding to %s" % url)
        cherrypy.lib.cptools.redirect(url, True)
    
    @classmethod
    def redirect(cls, path, params=None):
        ''' Redirect the current request to the given path '''
        url = BaseController._makeURL(path, params)
        Logger.debug("Redirecting to %s" % url)
        cherrypy.lib.cptools.redirect(url, False)
        