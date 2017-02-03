#!/usr/bin/env python
#
# This Module delivers the AIX Facts
# Build by Joris Weijters
#
#
DOCUMENTATION = '''
---
module: AIX_facts
version_added: "0.1"
short_description:
    This module gathers AIX facts. 
    It delivers the folowing ansible_facts:
    oslevel
    build
    lpps
    filesystems
    mounts
    vgs
    lssrc
    niminfo
'''

RETURN = '''
ansible_facts: {
    "oslevel": {
        "BUILD_DATE": "1543",
        "OS_Ver": "61",
        "SP": "06",
        "TL": "09",
        "oslevel-s": "6100-09-06-1543"
    },

    {
    "build": "2010_2"
    },
    
    {
    "lpps": [
        {
            "Automatic": "0",
            "Build_Date": "",
            "Description": "IBM BigFix Agent",
            "Destination_Dir.": " ",
            "EFIX_Locked": "0",
            "Fileset": "BESClient",
            "Fix_State": "C",
            "Install_Path": "/",
            "Level": "9.5.4.38",
            "Message_Catalog": " ",
            "Message_Number": " ",
            "Message_Set": " ",
            "PTF_Id": " ",
            "Package_Name": "BESClient",
            "Parent": " ",
            "State": " ",
            "Type": " ",
            "Uninstaller": " "
            },
    ]
    },

    {
    "filesystems": [
        {
            "Acct": "no",
            "AutoMount": "yes",
            "Device": "/dev/hd4",
            "MountPoint": "/",
            "Nodename": "",
            "Options": "rw",
            "Size": "524288",
            "Type": "bootfs",
            "Vfs": "jfs2"
        },
    ],
    },
    {
    "mounts": [
        {
            "device": "/dev/hd4",
            "fstype": "jfs2",
            "mount": "/",
            "options": "rw,log=/dev/hd8",
            "size_available": 172212224,
            "size_total": 268435456,
            "time": "Oct 12 15:14"
         },
    ],
    },
    {
    "vgs": {
        "midwarevg": [
            {
                "free_pps": "3",
                "pp_size": "128 megabyte(s)",
                "pv_name": "hdisk1",
                "pv_state": "active",
                "total_pps": "400"
            }
        ],
    ],
    },
    {
    "lssrc": [
        {
            "Group": "tcpip",
            "PID": "4260004",
            "Status": "active",
            "Subsystem": "named"
        },
    ]
    },

    {
    "niminfo": {
        "NIM_BOS_FORMAT": "rte",
        "NIM_BOS_IMAGE": "/SPOT/usr/sys/inst.images/installp/ppc/bos",
        "NIM_CONFIGURATION": "standalone",
        "NIM_FIPS_MODE": "0",
        "NIM_HOSTNAME": "rn12402pl.itc.testlab.intranet",
        "NIM_HOSTS": "127.0.0.1:loopback:localhost  172.27.8.43:rn12402pl.itc.testlab.intranet  172.27.8.18:rn100pgpl.itc.testlab.intranet",
        "NIM_MASTERID": "00F62C634C00",
        "NIM_MASTER_HOSTNAME": "rn100pgpl.itc.testlab.intranet",
        "NIM_MASTER_PORT": "1058",
        "NIM_MOUNTS": "",
        "NIM_NAME": "rn12402pl",
        "NIM_REGISTRATION_PORT": "1059",
        "NIM_SHELL": "nimsh",
        "ROUTES": "default:0:172.27.8.1"
    }
    }
}

opions:
  there are no options
'''

EXAMPLES = '''
- name: test
  hosts: all
  gather_facts: false
  tasks:
    - name: run AIX_facts
      action: AIX_facts_py

    - name: echo oslevel
      debug:
        var: oslevel
      when: oslevel.oslevel_s == "6100-09-06-1543"

    - name: printis It Works ! when  Build == 2010_2 and oslevel.oslevel_s = 6100-09-06-1543
      debug:
        msg: "It Works!"
      when:
        - build  == "2010_2"
        - oslevel.oslevel_s  == "6100-09-06-1543"


    - name: prints the version of openssl.base
      debug:
        var: item.Level
      with_items: "{{ lpps }}"
      when:
        - '"openssl.base" in "{{ item.Fileset|lower }}" '

'''

# import modules needed
import sys
import shlex
import os
import platform
import re
import itertools
import commands

try:
    import json
except ImportError:
    import simplejson as json

from ansible.module_utils.basic import AnsibleModule

# end import modules
# start defining the functions


# Internal functions
def _convert_out_to_list(out):
    """
    Internal function to convert colon separtated output to a list of dictionaries. 
    The first line of the out contains the keys, and starts with an '#' 
    F.i.
        #MountPoint:Device:Vfs:Nodename:Type:Size:Options:AutoMount:Acct
        /:/dev/hd4:jfs2::bootfs:524288:rw:yes:no
        /usr:/dev/hd2:jfs2::bootfs:8912896:rw:yes:no
    """
    lijst = []
    for line in out.splitlines():
        if re.match('^#', line):
             line = line[1:]
             line = line.replace(' ', '_')
             keys = line.split(":")
        else:
            values = line.split(":")
            adict = dict(itertools.izip(keys,values))
            lijst.append(adict)
    return lijst


def _get_mount_size_facts(mountpoint):
    """
    Internal module to determine the filesystem size and free size in bites 
    The input is teh mountpoint
    """
    size_total = None
    size_available = None
    try:
        statvfs_result = os.statvfs(mountpoint)
        size_total = statvfs_result.f_frsize * statvfs_result.f_blocks
        size_available = statvfs_result.f_frsize * (statvfs_result.f_bavail)
    except OSError:
        pass
    return size_total, size_available


def get_oslevel(module):
    """
    get the oslevel function delivers oslvel -s output
    <OS Ver>-<TL>-<SP>-<BUILD DATE>
    as wel OV_Version, the tecnology level, TL, the Servicepack, SP and the BUILD_DATE, 
    """
    rc, out, err = module.run_command(["/usr/bin/oslevel", "-s"])
    if rc !=0:
        module.fail_json(msg="could not determine oslevel", rc=rc, err=err) 	
    lijst = {'oslevel_s' : out.strip('\n') }
    keys=('OS_Ver', 'TL', 'SP', 'BUILD_DATE')
    values = out.split('-')
    v_stript = [v.rstrip('0\n') for v in values]
    adict = dict(itertools.izip(keys,v_stript))
    lijst.update(adict)

    return lijst


def get_build(module):
    """
    reads the /var/adm/autoinstall/etc/BUILD to determine the BUILS, 
    if this fails, it reads the /etc/BUILD
    the output is the BUILD version
    """
    build = {}
    org_file = '/var/adm/autoinstall/etc/BUILD'
    copy_file = '/etc/BUILD'
    try: 
        if os.path.exists(org_file):
            build = ''.join([line.strip() for line in open(org_file, 'r')])
    except IOError as e:
	if os.path.exists(copy_file):
            build = ''.join([line.strip() for line in open(copy_file, 'r')])
    except IOError as e:
	    module.fail_json(msg="could not determine BUILD", rc=rc, err=e)
    return build

def get_lpps(module):
    """
    runs the lslpp -Lc and delivers the output to _convert_out_to_list 
    for creating the lpps fact
    """
    lpps = []
    rc, out, err = module.run_command(["/usr/bin/lslpp", "-Lc"])
    if rc !=0:
         module.fail_json(msg="could not determine lslpp list", rc=rc, err=err)
    return  _convert_out_to_list(out)

def get_filesystems(module):
    """
    runs the lsfs -c and delivers the output to _convert_out_to_list 
    for creating the filesystems fact
    """
    filesystems = []
    rc, out, err =  module.run_command(["/usr/sbin/lsfs", "-c"])
    if rc !=0:
         module.fail_json(msg="could not determine lsfs list", rc=rc, err=err)
    return _convert_out_to_list(out)

def get_mounts(module):
    """
    create a lists with mounted filesystems
    it calls to _get_mount_size_facts to determine the size and free size
    it outputs all mounts
    """
    mounts = []
    # AIX does not have mtab but mount command is only source of info (or to use
    # api calls to get same info)
    rc, out, err = module.run_command("/usr/sbin/mount")
    if rc !=0:
        module.fail_json(msg="could not determine mounts", rc=rc, err=err)
    else:
        for line in out.splitlines():
            fields = line.split()
            if len(fields) != 0 and fields[0] != 'node' and fields[0][0] != '-' and re.match('^/.*|^[a-zA-Z].*|^[0-9].*', fields[0]):
                if re.match('^/', fields[0]):
                    # normal mount
                    size_total, size_available = _get_mount_size_facts(fields[1])
                    mounts.append({'mount': fields[1],
                                   'device': fields[0],
                                   'fstype' : fields[2],
                                   'options': fields[6],
                                   'size_total': size_total,
				   'size_available': size_available,
                                   'time': '%s %s %s' % ( fields[3], fields[4], fields[5])})
                else:
                    # nfs or cifs based mount
                    # in case of nfs if no mount options are provided on command line
                    # add into fields empty string...
                    if len(fields) < 8: fields.append("")
                    mounts.append({'mount': fields[2],
                                   'device': '%s:%s' % (fields[0], fields[1]),
                                   'fstype' : fields[3],
                                   'options': fields[7],
                                   'time': '%s %s %s' % ( fields[4], fields[5], fields[6])})
    return mounts

def get_vgs(module):
    """
    Get vg and pv Facts
    $ lsvg |xargs lsvg -p
    rootvg:
    PV_NAME           PV STATE          TOTAL PPs   FREE PPs    FREE DISTRIBUTION
    hdisk0            active            400         117         29..00..00..40..48
    midwarevg:
    PV_NAME           PV STATE          TOTAL PPs   FREE PPs    FREE DISTRIBUTION
    hdisk1            active            400         3           00..00..00..00..03
    altdiskvg:
    PV_NAME           PV STATE          TOTAL PPs   FREE PPs    FREE DISTRIBUTION
    hdisk2            active            399         399         80..80..79..80..80
    """

    lsvg_path = module.get_bin_path("lsvg")
    xargs_path = module.get_bin_path("xargs")
    cmd = "%s -o| %s %s -p" % (lsvg_path ,xargs_path,lsvg_path)
    vgs = {}
    if lsvg_path and xargs_path:
        rc, out, err = module.run_command(cmd,use_unsafe_shell=True)
	if rc !=0:
            module.fail_json(msg="could not determine lsvg |xargs lsvg -p", rc=rc, err=err)
        if rc == 0 and out:
            for m in re.finditer(r'(\S+):\n.*FREE DISTRIBUTION(\n(\S+)\s+(\w+)\s+(\d+)\s+(\d+).*)+', out):
                vgs[m.group(1)] = []
                pp_size = 0
                cmd = "%s %s" % (lsvg_path,m.group(1))
                rc, out, err = module.run_command(cmd)
                if rc == 0 and out:
                    pp_size = re.search(r'PP SIZE:\s+(\d+\s+\S+)',out).group(1)
                    for n in  re.finditer(r'(\S+)\s+(\w+)\s+(\d+)\s+(\d+).*',m.group(0)):
                        pv_info = { 'pv_name': n.group(1),
                                    'pv_state': n.group(2),
                                    'total_pps': n.group(3),
                                    'free_pps': n.group(4),
                                    'pp_size': pp_size
                                  }
                        vgs[m.group(1)].append(pv_info)
    return vgs


def get_lssrc(module):
    lijst = []
    rc, out, err = module.run_command(["/usr/bin/lssrc", "-a"])
    if rc !=0:
        module.fail_json(msg="ERROR: Could not complete lssrc ", rc=rc, err=err)
    firstline = True
    for line in out.splitlines():
        if firstline == True:
            keys = line.split()
            firstline = False
        else:
            # lssrc output is colomn formatted without specific separator, so use exact positions for each field!
            values = [ line[0:18].strip() , line[18:34].strip() , line[34:48].strip() , line[48:60].strip() ]
            adict = dict(itertools.izip(keys,values))
            lijst.append(adict)
    return lijst

def get_niminfo(module):
    file = '/etc/niminfo'

    try:
        if os.path.exists(file):
	    '''
	     the niminfo looks like:
	     #------------------ Network Install Manager ---------------
	     # warning - this file contains NIM configuration information
	     #       and should only be updated by NIM
	     export NIM_NAME=rn12402pl
	     export NIM_HOSTNAME=rn12402pl.itc.testlab.intranet
	     export NIM_CONFIGURATION=standalone
	     export NIM_MASTER_HOSTNAME=rn100pgpl.itc.testlab.intranet
	     export NIM_MASTER_PORT=1058
	     export NIM_REGISTRATION_PORT=1059
	     export NIM_SHELL="nimsh"
	     export NIM_MASTERID=00F62C634C00
	     export NIM_FIPS_MODE=0
	     export NIM_BOS_IMAGE=/SPOT/usr/sys/inst.images/installp/ppc/bos
	     export NIM_BOS_FORMAT=rte
	     export NIM_HOSTS=" 127.0.0.1:loopback:localhost  172.27.8.43:rn12402pl.itc.testlab.intranet  172.27.8.18:rn100pgpl.itc.testlab.intranet "
	     export NIM_MOUNTS=""
	     export ROUTES=" default:0:172.27.8.1 "

	     The next line will do 3 things
             It opens the file and removes all lines string with '#' ((l for l in open(file, 'r') if not l.startswith('    #')))
             it puts the output in line
	     It splits that line into 2 blocks showing only the second and splits this into 2 block with '=' as separator line.split(' ', 1)[1].split('=')
             the output is put into k anv v
	     than it strips k and v and creates a dictionary from these dict((k.strip(), v.strip(' "\n'))
	    '''
            niminfo = dict((k.strip(), v.strip(' "\n')) for k, v in (line.split(' ', 1)[1].split('=') for line in ((l for l in open(file, 'r') if not l.startswith('#')))))
    except IOError as e:
       module.fail_json(msg="could not read /etc/niminfo", rc=rc, err=e)
    return niminfo

                
	    

def main():
    module = AnsibleModule(argument_spec={})
    facts = {}
    facts["oslevel"] = get_oslevel(module)
    facts["build"] = get_build(module)
    facts["lpps"] = get_lpps(module)
    facts["filesystems"] = get_filesystems(module)
    facts["mounts"] = get_mounts(module)
    facts["vgs"] = get_vgs(module)
    facts["lssrc"] = get_lssrc(module)
    facts["niminfo"] = get_niminfo(module)

    module.exit_json(changed=False, rc=0, ansible_facts=facts)


if __name__ == '__main__':
    main()




