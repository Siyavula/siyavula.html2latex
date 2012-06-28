#!/usr/bin/env python

#
# Get and build the Grade 10 Life Science book from the community.siyavula.com site
#

import urllib
import os

from lxml import etree



# the life science book is built from plone folders
# the first level contains 4 and is \parts in latex
# the second level is chapters
# chapters contain sections
# each section is contained within in single html file
class part:
    def __init__(self, name, path):
        self.chapters = []
        self.name = name
        self.path = path

    def addSubPart(self, name, path):
        self.chapters.append(chaptername)


class book:
    def __init__(self):
        self.parts = []

    def addPart(self, part):
        '''partname is the folder name'''
        self.parts.append(part)


    def addSection(self, sectionname):
        self.chapters.append(sectionname)

#   def add(self, partname, depthname):
#       if depthname == 'part':
#           self.addPart(partname)
#       elif depthname == 'chapter':
#           self.addChapter(partname)
#       elif depthname == 'section':
#           self.add(

def filename2chaptername(name):
    '''change the file-name-string into File name string'''
    name = ' '.join(name.split('-'))
    name = name[0].upper() + name[1:]
    return name


def getdepth(dirname):
    '''Get nest depth to decide on part/chapter/section etc'''
    depth = len(dirname.split('/')) - 1
    return depth


depthname = {0:'', 1:'part', 2:'chapter', 3:'section'}


for dirpath, dirnames, filenames in os.walk('life-sciences-gr-10'):
    print dirpath
    depth = getdepth(dirpath)
    partname = dirpath.rpartition('/')[-1]
    if depth == 0:
        print "only 1"
        section_file = open(dirpath+'/'+partname+'.tex','w')
    else:
        section_file.write('  '*(depth) + ' \\%s{%s}\n'%(depthname[depth], filename2chaptername(partname)))


        # these are all sections contained in html files.
        if depth == 2:
            for f in filenames:
                if '.html' in f:
                    section_file.write('  '*depth + '\\section{' + filename2chaptername(f.replace('.html', ''))+'}\n')
                    section_file.write('  '*depth + '\\input{' + '/'.join(dirpath.split('/')[1:])+'/'+f.replace('.html', '')+'}\n')
                    #print "converting : ", dirpath+'/'+f
                    os.system('../bin/python ../html2latex.py %s' % dirpath+'/'+f)


#           section_file.write('\\chapter{%s}\n'%(filename2chaptername(partname)))
#           for t in texfiles:
#               section_file.write('\\section{%s}\n\\input{%s}\n'%(filename2chaptername(t), dirpath+'/'+t.replace('.tex', '')))

section_file.close()





