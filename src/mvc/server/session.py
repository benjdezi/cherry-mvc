'''
Created on Feb 24, 2012

User session management tools

@requires: CherryPy (http://docs.cherrypy.org/stable/intro/install.html)
@author: Benjamin Dezile
'''

import cherrypy
import base64

APP_COOKIE_KEY = "kac"
RM_KEY = "rm"
USER_SESSION_KEY = "_user"


def _get_session():
    ''' Return the current session '''
    cherrypy.lib.sessions.init()
    return cherrypy.session

def get_id():
    ''' Return the session id '''
    s = _get_session()
    return s.id

#### Session data methods ############

def put(key, value = None):
    ''' Save a value in session '''
    s = _get_session()
    s[key] = value
    s.save()
    
def get(key): 
    ''' Retrieve a session value '''
    s = _get_session()
    return s.get(key, None)

def has(key):
    ''' Return whether the current session has the given key '''
    s = _get_session() 
    v = s.get(key, None)
    return (v is not None)

def remove(key):
    ''' Remove the given key from session and return its associated value '''
    s = _get_session()
    v = s.pop(key)
    s.save()
    return v


#### Session user methods ############

def set_user(user):
    ''' Register user info into the current session '''
    put(USER_SESSION_KEY, user)

def remove_user():
    ''' Remove the current user info from the session '''
    remove(USER_SESSION_KEY)

def get_user():
    ''' Return the current user '''
    return get(USER_SESSION_KEY)

def has_user():
    ''' Return whether there's a registered user '''
    return has(USER_SESSION_KEY)

def assert_user_in_session():
    ''' Redirect to 403 if not user in session '''
    if not has_user():
        raise cherrypy.HTTPError(403, "Authentication required")


#### Session management methods ############

def expire():
    ''' Expire the current session '''
    remove_user()
    unset_remember_me()
    s = _get_session()
    s.clear()
    s.delete()
    cherrypy.lib.sessions.expire()


#### Cookie management methods #############

def get_cookie(key):
    ''' Get a cookie value '''
    c = cherrypy.request.cookie.get(key, None)
    return c.value if c else None

def set_cookie(key, value):
    ''' Set a cookie value '''
    cookie = cherrypy.response.cookie
    cookie[key] = str(value)
    cookie[key]['path'] = '/'
    cookie[key]['max-age'] = 3600 * 24 * 365
    cookie[key]['version'] = 1

def remove_cookie(key):
    ''' Remove a cookie and return its value '''
    v = cherrypy.request.cookie.get(key, None)
    if v is not None:
        del cherrypy.request.cookie[key]
    return v


#### Remember me methods ############

def _make_remember_me_token(user_id, user_pwd=None):
    ''' Return the remember me token for the given user '''
    return base64.b64encode("%s::%s" % (user_id, user_pwd if user_pwd else ""))

def _parse_remember_me_token(token):
    ''' Extract the remember me token '''
    return base64.b64decode(token).split("::")

def _get_remember_me_value():
    ''' Get the remember me cookie value '''
    return get_cookie(RM_KEY)

def set_remember_me(user_id, user_pwd=None):
    ''' Enable automatic session recovery '''
    set_cookie(RM_KEY, _make_remember_me_token(user_id, user_pwd))

def unset_remember_me():
    ''' Disable automatic session recovery '''
    remove_cookie(RM_KEY)

def has_remember_me():
    ''' Return whether session recovery is enabled '''
    return (get_cookie("rm") is not None)

def recover():
    ''' Recover user session if possible 
    Return user data upon success, False if the data was corrupted
    and None otherwise.
    '''
    if has_user():
        return
    rm = _get_remember_me_value()
    if rm:
        # Get remember me token
        corrupted = False
        rm_data = _parse_remember_me_token(rm)
        if rm_data and len(rm_data) == 2:
            user_id = int(rm_data[0])
            user_pwd = rm_data[1]
            # Return user data
            return (user_id, user_pwd if user_pwd else None)
        else:
            corrupted = True
        if corrupted:
            unset_remember_me()
            return False
