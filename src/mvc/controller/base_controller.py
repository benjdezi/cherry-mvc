'''
Created on Feb 24, 2012

@requires: CherryPy (http://docs.cherrypy.org/stable/intro/install.html)
@requires: py-utils (https://github.com/benjdezi/Python-Utils)
@author: Benjamin Dezile
'''

from pyutils.utils.logging import Logger
from pyutils.utils.config import Config
from mvc.controller.utils import format_http_args, render_template, format_async_response
from mvc.server import session
from urllib import urlencode
from time import time
import cherrypy
import inspect
import os


##  HELPERS  #################################

def _action_call_wrapper(f):
    ''' Monitor controller calls and performs some pre and post processing '''
    def wrapper(*kargs, **kwargs):
        
        inst = f.im_self
        name = f.__name__
        is_render_view = (name is "render_view")
        is_async = (hasattr(f, 'is_async') and f.is_async is True)
        is_action = (is_render_view or is_async)
        
        # Session recovery
        try:
            user_data = session.recover()
            if user_data:
                inst._session_recovery(inst, user_data[0], user_data[1])
        except Exception, e:
            Logger.error("Could not recover session", e)  
        
        # Format arguments
        formatted_kargs = format_http_args(kwargs)
        
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
    try:
        res = f(**args)
        data = res if res is not None else {}
        json_resp = format_async_response(data)
    except cherrypy.HTTPError, e:
        raise e
    except Exception, e:
        Logger.error("Error while processing call to %s" % f.__name__, e)
        json_resp = format_async_response(None, False, e)
    if Config.is_dev():
        Logger.debug("Async response to %s: %s" % (f.__name__, json_resp))
    return json_resp


##  CONTROLLER  #################################

class BaseController(object):
    ''' Base controller
    Abstract base for all controllers.
    Contains all sorts of helpers and structures that may be needed in controllers.
    '''
    
    instances = dict()
    web_dir = None
    
    def __init__(self, name, path):
        self.name = name
        self.path = path
        # Automatically add call monitoring to instance methods
        # except one starting with _ (considered internal)
        for x in inspect.getmembers(self, (inspect.ismethod)):
            if hasattr(BaseController, x[0]):
                # Ignore methods from BaseController
                continue
            if not x[0].startswith('_'):
                attr = getattr(self, x[0])
                setattr(self, x[0], _action_call_wrapper(attr))
        BaseController.instances[path] = self
        self.log("Created new controller")
        
    def _before_action(self, action_name, **action_args):
        ''' Called right before an action is executed '''
        pass
    
    def _after_action(self, action_name, **action_args):
        ''' Called right after an action is executed '''
        pass
        
    def _session_recovery(self, user_id, user_token):
        ''' Called upon success session recovery. 
        This should be overridden using set_session_recovery_handler.
        '''
        pass
        
    def set_session_recovery_handler(self, handler):
        ''' Set the session recovery handling method '''
        self._session_recovery = handler
        
    def set_web_dir(self, path):
        ''' Set the path to the web directory, 
        this will be used in rendering templates.
        '''
        self.__class__.web_dir = path
        
    def log(self, msg):
        ''' Log a message using basic server logging '''
        cherrypy.log("%s - %s" % (self.name, msg))
        
    def get_path(self):
        ''' Return the associated path '''
        return self.path
        
    def get_name(self):
        ''' Return the controller's name '''
        return self.name
    
    def get_remote_ip(self):
        ''' Return the IP address of the remote client '''
        return self.get_remote_address()[0]
    
    def get_remote_address(self):
        ''' Return the address and port of the remote client for the current request '''
        req = self.get_request()
        return (req.remote.ip, req.remote.port)
    
    def get_socket(self):
        ''' Return the socket associated with the current request '''
        req = self.get_request()
        return req.rfile.rfile._sock
    
    def get_response(self):
        ''' Return the current response '''
        return cherrypy.response
    
    def get_request(self):
        ''' Return the current request '''
        return cherrypy.request
    
    def get_headers(self):
        ''' Return the headers from the current request '''
        req = self.get_request()
        return req.headers  
    
    @classmethod
    def render_view(cls, view_rel_path, params=dict()):
        ''' Render a view with the given parameters '''
        if not cls.web_dir:
            raise Exception("Web dir path not set")
        full_path = os.path.join(cls.web_dir, "views", view_rel_path)
        return render_template(full_path, params)
    
    @classmethod
    def send_error(cls, status=500, msg=None):
        ''' Return an error for the current request '''
        if not msg:
            if status == 404:
                msg = "Page not found"
            elif status == 500:
                msg = "Server error"
            else:
                msg = "Unknown error"
        Logger.error("HTTP %s%s" % (status, (": " + msg if msg else "")))
        raise cherrypy.HTTPError(status, msg)
    
    @classmethod
    def _make_url(cls, path, params=None):
        ''' Build a full url out of a path and parameters '''
        qs = urlencode(params) if params else ""
        path = path.strip("/")
        return ("/" + path if path else "/") + ("?" + qs if qs else "")
    
    @classmethod
    def forward(cls, controller, action=None, params=None):
        ''' Forward the current request to the given action '''
        action = action if action else "index"
        controller_inst = cls.instances[controller]
        if not controller_inst:
            cls.send_error(404, "Controller %s does not exist" % controller)
        try:
            action_meth = getattr(controller_inst, action)
            Logger.info("Forwarding to %s > %s with params = %s" % (controller, action, params)) 
            return action_meth(**params)
        except AttributeError:
            cls.send_error(404, "%s/%s does not exist" % (controller, action))
        except BaseException, e:
            Logger.error("Error while forwarding to %s > %s" % (controller, action), e)
            cls.send_error(500)
    
    @classmethod
    def redirect(cls, path, params=None):
        ''' Redirect the current request to the given path '''
        url = BaseController._make_url(path, params)
        Logger.info("Redirecting to %s" % url)
        cherrypy.lib.cptools.redirect(url, False)
        