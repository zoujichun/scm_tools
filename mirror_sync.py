#!/usr/bin/env python
# -*- coding:utf8 -*-
# Author: zoujichun3166@gmail.com

import os
from sys import exit, stderr
from optparse import OptionParser
from multiprocessing import Pool, TimeoutError
from subprocess import Popen, PIPE, check_call, CalledProcessError
import re

class SyncError(Exception):
    def __init__(self, msg):
        super(type(self), self).__init__(msg)
        self.__msg = msg

    def __str__(self):
        return 'Error: ' + self.__msg

def get_projects(ip, port, user):
    args = ['ssh',
            '-p',
            port,
            '%s@%s' %(user, ip),
            'gerrit',
            'ls-projects'
            ]
    p = Popen(args, shell=False, stdout=PIPE, stderr=PIPE)
    (_out, _err) =  p.communicate()
    return set(sorted(_out.splitlines()))

def sync_git(cwd, ip, port, user, project, branch, gc=False, no_fetch_tag=False):
    gitdir = cwd + '/' + project + '.git'

    ref_pair = []
    if len(branch) > 0:
        for b in branch:
            try:
                git_ls_remote = ['git', 'ls-remote', 
                        'ssh://%s@%s:%s/%s.git' %(user, ip, port, project),
                        'refs/heads/*']
                p = Popen(git_ls_remote, shell=False, stdout=PIPE, stderr=PIPE)
                _o = p.communicate()[0]
                if len(_o.strip()) != 0:
                    _r = re.compile('refs/heads/%s$' %(b))
                    for _l in _o.splitlines():
                        _m = _r.search(_l)
                        if _m:
                            ref_pair.append("+%s:%s" %(_m.group(), _m.group()))
            except:
                pass
    else:
        ref_pair = ['+refs/heads/*:refs/heads/*']
    if len(ref_pair) > 0:
        try:
            if not os.path.isdir(gitdir):
                os.makedirs(gitdir)
                git_init = ['git', 'init', '--bare', gitdir]
                check_call(git_init)
                print 'New git created: %s' %(project)

            print 'Fetching repository %s ...' %(project)
            os.chdir(gitdir)
            git_fetch = ['git', 'fetch',
                    'ssh://%s@%s:%s/%s.git' %(user, ip, port, project)] + ref_pair
            if no_fetch_tag:
                git_fetch.append('-n')

            check_call(git_fetch)
            check_call(['git', 'pack-refs', '--all'])
            if gc:
                check_call(['git', 'gc'])
        except CalledProcessError as e:
            print >>stderr, e
            raise SyncError('Sync %s failed' %(project))

def main():
    parser = OptionParser()
    parser.set_defaults(o=os.getcwd(), j=2, branch=[])
    parser.add_option('-s', action='store', dest="host",
                      help='host')
    parser.add_option('-p', action='store', dest="port",
                      help='port')
    parser.add_option('-u', action='store', dest="user",
                      help='user')
    parser.add_option('-c', action='store_true', dest="gc", default=False,
                      help='gc?')
    parser.add_option('-n', action='store_true', default=False,
                      help='pass through -n to git fetch?')
    parser.add_option('-b', action='append', dest="branch",
            help='branch')
    parser.add_option('-i', action='append', dest="ignore",
            help='ignore project(-i project1 -i project2)')
    parser.add_option('-o', metavar='<dir>',
            help='source_out')
    parser.add_option('-j', metavar='<num>', type='int',
                      help='jobs')
    (opt, args) = parser.parse_args()
    if not opt.host:
        exit("host(-s) is required.")
    if not opt.port:
        exit("port(-p) is required.")
    if not opt.user:
        exit("user(-u) is required.")

    projects=get_projects(opt.host, opt.port, opt.user)
    if opt.ignore:
        projects = set(projects) - set(opt.ignore)

    if opt.j > 1:
        pool = Pool(processes=opt.j)
        result = []
        for p in projects:
            ar = pool.apply_async(sync_git, (opt.o, opt.host, opt.port, opt.user, p, opt.branch, opt.gc, opt.n))
            result.append(ar)
        for r in result:
            r.wait(10*60)
    else:
        for p in projects:
            sync_git(opt.o, opt.host, opt.port, opt.user, p, opt.branch, opt.gc, opt.n)

if __name__ == "__main__":
    main()
