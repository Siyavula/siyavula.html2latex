import sys
import os
import string

import plasTeX.TeX as TeX
from plasTeX.Renderers import Renderer
from plasTeX.Base import Environment

class activity(Environment):
    args = ' title:str '

class Renderer(Renderer):
    def default(self, node):
        """ Rendering method for all non-text nodes """
        s = []
        ignore = False

        # Handle characters like \&, \$, \%, etc.
        if len(node.nodeName) == 1 and node.nodeName not in string.letters:
            return self.textDefault(node.nodeName)

        # Start tag
        if not ignore:
            s.append('<%s>' % node.nodeName)

        # See if we have any attributes to render
        if node.hasAttributes():
            for key, value in node.attributes.items():
                # If the key is 'self', don't render it
                # these nodes are the same as the child nodes
                if key == 'self':
                    continue
                if key == 'title':
                    s.append('<%s>%s</%s>' % (key, unicode(value), key))

                else:
                    print key, value

        # Invoke rendering on child nodes
        s.append(unicode(node))

        # End tag
        if not ignore:
            s.append('</%s>' % node.nodeName)
        return u'\n'.join(s)

    def textDefault(self, node):
        """ Rendering method for all text nodes """
        return node.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

    def section(self, node):
        return u'\n<section type="%s">%s</section>'%(node.nodeName, unicode(node))

    def par(self, node):
        if node.parentNode == 'par':
            return unicode(node)
        else:
            if unicode(node).strip() == '':
                return u''
            else:
                return u'\n<para>%s</para>'%unicode(node)

    def itemize(self, node):
        return u'\n<list list-type="bulleted">%s</list>'%unicode(node)

    def enumerate(self, node):
        return u'\n<list list-type="enumerated">%s</list>'%unicode(node)
    
    def keyconcepts(self, node):
        return u'\n<note type="keyconcepts">%s</note>'%(unicode(node))

    def newwords(self, node):
        return u'\n<note type="newwords">%s</note>'%(node.attributes['text'])

    def bgroup(self, node):
        if node.parentNode.nodeName == 'par':
            return unicode(node)
        else:
            return '<bgroup>%s</bgroup>'%unicode(node)

    def textit(self, node):
        return u'<emphasis effect="italics">%s</emphasis>'%unicode(node)

    def textbf(self, node):
        return u'<emphasis effect="bold">%s</emphasis>'%unicode(node)

    def displaymath(self, node):
        return u'\n<latex display="block">%s</latex>'%unicode(node)

    def textrm(self, node):
        return u'\\textrm{%s}'%unicode(node)

    def sub(self, node):
        return u'_%s'%unicode(node)

    def definition(self, node):
        # this one is dodgy, it may break, only works on my (ewald's) html2latex output.
        # Term is the bold part
        
        # find the term. its the next textbf element
        term = node.nextSibling
        while term != None:
            if term.nodeName == 'textbf':
                break
            else:
                term = term.nextSibling
        # find the meaning
        try:
            meaning = term.nextSibling.textContent
            term.parentNode.remove(term)
            meaning.parentNode.remove(meaning)
        except AttributeError: 
            meaning = ''

        if (term != None) and (meaning.strip()!=''):
            return u'\n<definition>\n    <term>%s</term>\n    <meaning>%s</meaning>\n</definition>'%(unicode(term), unicode(meaning))
        else:
            return ''

    def center(self, node):
        return unicode(node)

    def hrule(self, node):
        return u''
    
    def hline(self, node):
        return u''

    def tabularnewline(self, node):
        return u''
    
    def longtable(self, node):
        return u'\n<table><tgroup><tbody>%s</tbody></tgroup></table>\n'%(unicode(node))

    def ArrayRow(self, node):
        return u'\n<row>%s</row>'%(unicode(node))

    def ArrayCell(self, node):
        return u'\n<entry>%s</entry>'%(unicode(node))

    def includegraphics(self, node):
        return u'\n<media>\n    <image src="%s"/>\n</media>'%(node.attributes['src'])

    def visit(self, node):
        return u'\n<note type="visit">%s</note>'%unicode(node)

    def activity(self, node):
        return u'\n<activity type="activity">\n<title>%s</title>%s</activity>'%(node.attributes['title'],unicode(node))

if __name__ == "__main__":
    inputfile = sys.argv[1]

    latexcontent = open(inputfile, 'r').read()
    latexcontent = r'''\documentclass{book}
    
    \usepackage{latex2cnxmlmod}
    \usepackage{longtable}
    
    \begin{document}
    %s
    \end{document}'''%latexcontent

    tex = TeX.TeX()
    tex.ownerDocument.config['files']['split-level'] = -100
    tex.ownerDocument.config['files']['filename'] = '%s.xml'%inputfile
    tex.input(latexcontent)

    document = tex.parse()
    # Render the document
    renderer = Renderer()
    renderer['chapter'] = renderer.section
    renderer['section'] = renderer.section
    renderer['subsection'] = renderer.section
    renderer['subsubsection'] = renderer.section
    renderer['par'] = renderer.par
    renderer['itemize'] = renderer.itemize
    renderer['keyconcepts'] = renderer.keyconcepts
    renderer['newwords'] = renderer.newwords
    renderer['bgroup'] = renderer.bgroup
    renderer['textbf'] = renderer.textbf
    renderer['textit'] = renderer.textit
    renderer['displaymath'] = renderer.displaymath
    renderer['textrm'] = renderer.textrm
    renderer['active::_'] = renderer.sub
    renderer['center'] = renderer.center
    renderer['hrule'] = renderer.hrule
    renderer['hline'] = renderer.hline
    renderer['tabularnewline'] = renderer.tabularnewline
    renderer['longtable'] = renderer.longtable
    renderer['ArrayCell'] = renderer.ArrayCell
    renderer['ArrayRow'] = renderer.ArrayRow
    renderer['includegraphics'] = renderer.includegraphics
    renderer['visit'] = renderer.visit
    renderer['activity'] = renderer.activity


    renderer.render(document)

