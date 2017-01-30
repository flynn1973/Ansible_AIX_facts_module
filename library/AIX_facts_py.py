#!/usr/bin/env python
#
# This Module delivers the AIX Facts
# Build by Joris Weijters
#
#
DUCUMENTATION = '''
---
module: AIX_facts
version_added: "0.1"
short_description:
    - get AIX facts
      oslevel


opions:
  there are no options
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
    get the oslevel functio delivers oslvel -s output
    """
    rc, out, err = module.run_command(["/usr/bin/oslevel", "-s"])
    if rc !=0:
        module.fail_json(msg="could not determine oslevel", rc=rc, err=err) 	
    return out


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
            build = open(org_file, 'r').readlines()
    except IOError as e:
	if os.path.exists(copy_file):
            build = open(copy_file, 'r').readlines()
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

def main():
    module = AnsibleModule(argument_spec={})
    facts = {}
    facts["oslevel"] = get_oslevel(module)
    facts["build"] = get_build(module)
    facts["lpps"] = get_lpps(module)
    facts["filesystems"] = get_filesystems(module)
    facts["mounts"] = get_mounts(module)
    facts["vgs"] = get_vgs(module)

    module.exit_json(changed=False, rc=0, ansible_facts=facts)


if __name__ == '__main__':
    main()




