#!/usr/bin/env python
# -*- coding:utf8 -*-
# Author: zoujichun3166@gmail.com

import os
import sys
import json
from optparse import OptionParser

def die(msg):
    print >>sys.stderr, 'Fatal: %s' %(msg)
    sys.exit(1)

def get_ssh_info(gerrit_url, gerrit_user):
    p = os.popen('wget -q -O - %s/ssh_info' % (gerrit_url))
    ssh_info = p.read().strip()
    p.close()
    if len(ssh_info) == 0:
        die("fatal: Can't get ssh_info from %s." %(gerrit_url))
    ip = ssh_info.split()[0]
    port = ssh_info.split()[1]
    return (ip, port)

def query_gerrit(ip, port, gerrit_user, changeid):
    query_cmd = 'ssh -p %s %s@%s gerrit query %s --format=JSON --current-patch-set' %(port, gerrit_user, ip, changeid)
    p = os.popen(query_cmd)
    query_ret_json = p.read().splitlines()
    e = p.close()
    if e is not None:
        die("run gerrit query failed.")
    if len(query_ret_json) != 2:
        die("Can't find %s" %(changeid))
    query_ret = json.loads(query_ret_json[0])
    crvw_value = 0
    try:
        number = query_ret['number']
        currentPatchSet = query_ret['currentPatchSet']
        status = query_ret['status']
    except KeyError:
        die("Can't get currentPatchSet from %s." %(changeid))
    return {'changeid':changeid, 'number':number, 'status':status, 'currentPatchSet':currentPatchSet}

#################################
usage='%prog -u gerrit_user -r gerrit_url -c gerrit_id -a action -s score -m message'
parser = OptionParser(usage=usage)
parser.add_option("-u","--user",
        action="store", type="string", dest="user",
        help="gerrit login username")
parser.add_option("-r","--url",
        action="store", type="string", dest="url",
        help="gerrit url")
parser.add_option("-c","--changeid",
        action="store", type="string", dest="changeid",
        help='''change number, you can specify patchset number, if not, will use current patchset. eg: 1234,2''')
parser.add_option("-a","--action",
        action="store", type="string", dest="action",
        help="gerrit action, review, verify, submit, abandon, message, flush-caches")
parser.add_option("-s","--score",
        action="store", type="string", dest="score",
        help="Code review's score, +1, -1, +2")
parser.add_option("-m","--message",
        action="store", type="string", dest="msg",
        help="message content")
(opt, args) = parser.parse_args()
if not opt.user:
    die('gerrit login username(-u) is required.')
if not opt.url:
    die('gerrit url(-r) is required.')
if opt.action != 'flush-caches':
    if not opt.changeid:
        die('Change-Id(-c) is required.')
if not opt.action:
    die('gerrit action(-a) is required.')
if opt.action == 'review':
    if not opt.score:
        die("Code review's score(-s) is required when you pull the review trigger.")

gerrit_user = opt.user
gerrit_url  = opt.url
gerrit_id   = opt.changeid
action      = opt.action
score       = opt.score
msg         = opt.msg

(ip, port) = get_ssh_info(gerrit_url, gerrit_user)
if action == 'flush-caches':
    flush_cmd = 'ssh -p %s %s@%s gerrit flush-caches --all' %(port, gerrit_user, ip)
    e = os.system(flush_cmd)
    if e != 0:
        die("flush-caches failed.")
    sys.exit(0)

has_patchset_num = False
if gerrit_id.find(',') > 0:
    has_patchset_num = True
    patchset_number = gerrit_id.split(",")[1]
    gerrit_id = gerrit_id.split(",")[0]

query_ret = query_gerrit(ip, port, gerrit_user, gerrit_id)
# if dont have patchset number, using current patchset number
if not has_patchset_num:
    gerrit_id = query_ret['number']
    patchset_number = query_ret['currentPatchSet']['number']
status = query_ret['status']

is_closed = False
if status == 'MERGED' or status == 'ABANDONED':
    is_closed = True

approve_cmd = 'ssh -p %s %s@%s gerrit review %s,%s ' %(port, gerrit_user, ip, gerrit_id, patchset_number)
if action == 'review':
    if is_closed:
        print >>sys.stderr, 'change %s cloesed.' %(gerrit_id)
        sys.exit(0)
    review_cmd = approve_cmd + '''--code-review %s -m '"%s"' ''' %(score, msg)
    e = os.system(review_cmd)
    if e != 0:
        die("review failed.")
elif action == 'verify':
    if is_closed:
        print >>sys.stderr, 'change %s cloesed.' %(gerrit_id)
        sys.exit(0)
    if not opt.score:
        score = '+1'
    verify_cmd = approve_cmd + '''--verified %s -m '"%s"' ''' %(score, msg)
    e = os.system(verify_cmd)
    if e != 0:
        die("verify failed.")
elif action == 'submit':
    if is_closed:
        print >>sys.stderr, 'change %s cloesed.' %(gerrit_id)
        sys.exit(0)
    submit_cmd = approve_cmd + '--submit'
    e = os.system(submit_cmd)
    if e != 0:
        die("submit failed.")
elif action == 'abandon':
    if is_closed:
        print >>sys.stderr, 'change %s cloesed.' %(gerrit_id)
        sys.exit(0)
    abandon_cmd = approve_cmd + '--abandon'
    os.system(abandon_cmd)
elif action == 'message':
    message_cmd = approve_cmd + ''' -m '"%s"' ''' %(msg)
    os.system(message_cmd)
