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
    v = s.get(key,None)
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
    s = _get_session()
    s.expire()


#### App cookie methods ############

def _get_app_cookie_values():
    ''' Return the application cookie value '''
    cookie = cherrypy.request.cookie.get(APP_COOKIE_KEY, None)
    if cookie:
        values = dict()
        for entry in cookie.value.split("@@"):
            pair = entry.split("::")
            if pair and len(pair) == 2:
                values[pair[0]] = pair[1]
        return values

def _set_app_cookie_values(values):
    ''' Set the application cookie value '''
    v = list()
    for k in values:
        v.append(k + "::" + values[k])
    cookie = cherrypy.response.cookie
    cookie[APP_COOKIE_KEY] = "@@".join(v)
    cookie[APP_COOKIE_KEY]['path'] = '/'
    cookie[APP_COOKIE_KEY]['max-age'] = 3600 * 24 * 365
    cookie[APP_COOKIE_KEY]['version'] = 1

def get_cookie(key):
    ''' Get a cookie value '''
    values = _get_app_cookie_values()
    if values:
        return values.get(key, None)

def set_cookie(key, value):
    ''' Set a cookie value '''
    values = _get_app_cookie_values()
    if not values:
        values = dict()
    values[key] = value
    _set_app_cookie_values(values)

def remove_cookie(key):
    ''' Remove a cookie and return its value '''
    values = _get_app_cookie_values()
    if values:
        v = values[key]
        del values[key]
        _set_app_cookie_values(values)
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
    rm = _get_remember_me_value()
    if rm and not has_user():
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
