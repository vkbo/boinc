#!/usr/bin/env python

# $Id$

'''
add items to the BOINC database.

Usages:

add.py project      --name=yah --long_name="YETI @ home"

add.py platform     --name=c64 [ --user_friendly_name="Commodore 64" ]

add.py core_version --platform=c64 --version_num=717
                    --exec_file=/path/to/boinc_7.17_c64
                    [--message="Message"] [--message_priority="Priority"]

add.py app          --name=YetiApp [--min_version=716]

add.py app_version  --app=YetiApp --platform=c64 --version_num=717
                    --exec_file=/path/to/yeti_7.17_c64
                      [--signature_file=/path/to/sig_file]
                    [--exec_file=/path/to/more_bins
                      [--signature_file=/tmp/sig_file2]] ...

add.py user         --name="Carl Sagan" --email_addr="carl.sagan@example.com"
                    --authenticator="deadbeef"
                    [--country=Estonia --postal_code=94703
                     --global_prefs_file=/path/to/prefs.xml]

add.py workunit  (TODO)

add.py result    (TODO) '''

import boinc_path_config
from Boinc import database, db_mid, configxml, tools
from Boinc.util import *
import sys, os, getopt, time, pprint

CREATE_TIME = ['?create_time', int(time.time())]

class XCoreVersion(database.CoreVersion):
    def __init__(self,**kwargs):
        kwargs['xml_doc'] = tools.process_executable_file(kwargs['exec_file'])
        del kwargs['exec_file']
        apply(database.CoreVersion.__init__,[self],kwargs)

class XAppVersion(database.AppVersion):
    def __init__(self,**kwargs):
        kwargs['xml_doc'] = tools.process_app_version(
            app = kwargs['app'],
            version_num = int(kwargs['version_num'])
            exec_files = kwargs['exec_files']
            signature_files = kwargs.get('signature_files',{}))
        del kwargs['signature_files']
        del kwargs['exec_files']
        del kwargs['exec_file']
        apply(database.AppVersion.__init__,[self],kwargs)

# format: [ database.Object, args, ...]
#   arg format:
#       'arg'
#       '?arg'    optional
#       [ 'arg', default_value ]
list_objects_to_add = [
    [ database.Project,    'name', '?long_name' ],
    [ database.Platform,   'name', 'user_friendly_name', CREATE_TIME ],
    [ XCoreVersion, 'platform', 'version_num', 'exec_file',
      ['?message',''], ['?message_priority','']],
    [ database.App,        'name', ['?min_version',0], CREATE_TIME],
    [ XAppVersion, 'app', 'platform', 'version_num', 'exec_file', '?signature_file',
      CREATE_TIME ],
    [ database.User,       'name', 'email_addr', 'authenticator',
      ['?country','United States'], ['?postal_code','94703'],
      '?global_prefs', '?global_prefs_file',
      CREATE_TIME ],
    # [ database.Workunit,   'zzzz' ],
    ]

most_recent_exec_file = None

def translate_arg(object, arg, value, args_dict):
    '''Translate various arguments'''
    database_table = None
    try:
        database_table = database.__dict__[arg.capitalize()]._table
    except:
        pass
    if database_table:
        return (arg,translate_database_arg(database_table, arg, value))

    if arg == 'global_prefs_file':
        return ('global_prefs', open(value).read())

    if object.DatabaseObject == XAppVersion:
        # 'add app_version' accepts multiple '-exec_file's with
        # '-signature_file' applying to the most recent exec_file
        if arg == 'exec_file':
            global most_recent_exec_file
            most_recent_exec_file = value
            args_dict.setdefault('exec_files',[]).append(value)
            # since this is required, set it to None so that argument checker
            # knows we got one; we'll delete it later.
            return (arg,None)
        if arg == 'signature_file':
            args_dict.setdefault('signature_files',{})[most_recent_exec_file] = value
            return (None,None)

    return (arg,value)


def translate_database_arg(database_table, arg, value):
    '''Accept e.g. either --app Astropulse or --app 1'''
    try:
        id = int(value)
        results = database_table.find(id=id)
        if not results:
            raise Exception("")
    except:
        results = database_table.find(name=value)
    if len(results) == 0:
        raise SystemExit('No %s "%s" found' %(arg,value))
    if len(results) > 1:
        print >>sys.stderr, 'Too many %ss match "%s": '%(arg,value)
        for result in results:
            print  >>sys.stderr, '   ', result.name
        raise SystemExit
    return results[0]

def ambiguous_lookup(string, dict):
    results = []
    string = string.replace('_','')
    for key in dict:
        k = key.replace('_','')
        if k == string:
            return [dict[key]]
        if k.startswith(string):
            results.append(dict[key])
    return results


def parse_global_options(args):
    # raise SystemExit('todo')
    pass

def dv(object,arg):
    if arg in object.default_values:
        return '    --%s [%s]' %(arg, object.default_values[arg])
    else:
        return '    --%s' %arg

def help_object(object, msg=None):
    if msg:
        print >>sys.stderr, "add:", msg
        print
    print >>sys.stderr, "Syntax: add.py %s"%object.name
    for arg in object.args:
        print >>sys.stderr, dv(object,arg)
    print >>sys.stderr, " Optional:"
    for arg in object.optional_args:
        print >>sys.stderr, dv(object,arg)
    raise SystemExit

def add_object(object, args):
    try:
        parsed_opts, placement_args = \
                     getopt.getopt(args, '',
                                   map(lambda s: s+'=',
                                       object.args + object.optional_args))
        if placement_args:
            raise getopt.GetoptError('Unknown args '+' '.join(placement_args))
    except getopt.GetoptError, e:
        help_object(object, e)
    args_dict = object.default_values.copy()
    for arg,value in parsed_opts:
        if not arg.startswith('--'):
            raise Exception('internal error: arg should start with "--"')
        arg = arg[2:]
        (arg,value) = translate_arg(object,arg,value,args_dict)
        if not arg: continue
        args_dict[arg] = value
    for arg in object.args:
        if not arg in args_dict:
            help_object(object, 'required argument --%s not given'%arg)

    object = apply(object.DatabaseObject, [], args_dict)
    object.commit()
    print "Committed", object, "with args:"
    pprint.pprint(object.__dict__)

class Dict:
    pass

objects_to_add = {}
for o in list_objects_to_add:
    object = Dict()
    object.DatabaseObject = o[0]
    object.name = object.DatabaseObject._table.table
    object.args = []
    object.optional_args = []
    object.default_values = {}
    for arg in o[1:]:
        if isinstance(arg, list):
            default_value = arg[1]
            arg = arg[0]
        else:
            default_value = None
        if arg.startswith('?'):
            optional = True
            arg = arg[1:]
        else:
            optional = False
        if optional:
            object.optional_args.append(arg)
        else:
            object.args.append(arg)
        if default_value:
            object.default_values[arg] = default_value
    objects_to_add[object.name] = object

if len(sys.argv) < 2:
    print >>sys.stderr, """Syntax: add.py <object_to_add> <options...>

Adds an object to the BOINC database.

Objects to add:"""
    for object in sorted_keys(objects_to_add):
        print >>sys.stderr, "    ", object
    print >>sys.stderr, """
Global options:
     --config=config.xml Path to configuration file.

These override config.xml:
     --db_name           Database name
     --db_password       Database password
     --db_user           Database user

For command-line help on a particular object, use add <object> without further
arguments.
"""

    raise SystemExit(1)

name_of_object_to_add = sys.argv[1].strip().lower()

possible_objects = ambiguous_lookup(name_of_object_to_add, objects_to_add)
if len(possible_objects) == 0:
    raise SystemExit("No such object '%s' to add"%name_of_object_to_add)
if len(possible_objects) > 1:
    print >>sys.stderr, "Object name '%s' matches multiple objects:"%name_of_object_to_add
    for object in possible_objects:
        print "    ", object.name
    raise SystemExit(1)

args = sys.argv[2:]
parse_global_options(args)

config = configxml.default_config()
database.connect(config.config)

add_object(possible_objects[0], args)
