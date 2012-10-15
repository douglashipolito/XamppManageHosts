from distutils.core import setup
import py2exe
setup(console=[{ "script" : "managehosts.py", 'uac_info': "requireAdministrator"}])