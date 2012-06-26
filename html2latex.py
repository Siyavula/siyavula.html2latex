# -*- coding: utf-8 -*-
#
# Convert html with special css classes to Customized LaTeX environments.
#
import sys
import os
import re, htmlentitydefs
import urllib

from lxml import etree
from jinja2 import Template, FileSystemLoader, Environment
from jinja2.exceptions import TemplateNotFound
from PIL import Image

# Some boilerplate to use jinja more elegantly with LaTeX
# http://flask.pocoo.org/snippets/55/


LATEX_SUBS = (
    (re.compile(r'\\'), r'\\textbackslash'),
    (re.compile(r'([{}_#%&$])'), r'\\\1'),
    (re.compile(r'~'), r'\~{}'),
    (re.compile(r'\^'), r'\^{}'),
    (re.compile(r'"'), r"''"),
    (re.compile(r'\.\.\.+'), r'\\ldots'),
)

def escape_tex(value):
    newval = value
    for pattern, replacement in LATEX_SUBS:
        newval = pattern.sub(replacement, newval)
    return newval

def etree_in_context(iNode, iContext):
    parent = iNode.getparent()
    while parent is not None:
        if parent.tag == iContext:
            return True
        parent = parent.getparent()
    return False


def transform(dom):
        # Currency
        for currencyNode in dom.xpath('//currency'):
            latexMode = etree_in_context(currencyNode, 'latex')
            symbolNode = currencyNode.find('symbol')
            if symbolNode is None:
                symbol = 'R'
                symbolLocation = 'front'
            else:
                symbol = symbolNode.text.strip()
                symbolLocation = symbolNode.attrib.get('location', 'front')
            numberNode = currencyNode.find('number')
            if numberNode.text is None:
                numberNode.text = ''
            # Set default precision to 0 if number is an int, and to 2 if it is a float
            try:
                int(numberNode.text.strip())
                defaultPrecision = 0
            except ValueError:
                defaultPrecision = 2
            currencyPrecision = int(currencyNode.attrib.get('precision', defaultPrecision))
            numberNode.text = ("%%.%if"%currencyPrecision)%float(numberNode.text.strip())

            replacementNode = etree.Element('dummy')
            if symbolLocation == 'front':
                if latexMode:
                    replacementNode.text = r'\text{' + symbol + ' }'
                else:
                    replacementNode.text = symbol + u'\u00a0'
                replacementNode.append(numberNode)
            else:
                replacementNode.append(numberNode)
                if latexMode:
                    replacementNode.tail = r'\text{ ' + symbol + '}'
                else:
                    replacementNode.tail = u'\u00a0' + symbol
            etree_replace_with_node_list(currencyNode.getparent(), currencyNode, replacementNode)

        # Percentage
        for percentageNode in dom.xpath('//percentage'):
            latexMode = etree_in_context(percentageNode, 'latex')
            percentageNode.tag = 'number'
            if percentageNode.tail is None:
                percentageNode.tail = ''
            if latexMode:
                percentageNode.tail = r'\%' + percentageNode.tail
            else:
                percentageNode.tail = '%' + percentageNode.tail

        # United numbers: ensure that units follow numbers
        for node in dom.xpath('//unit_number'):
            if (len(node) == 2) and (node[0].tag == 'unit') and (node[1].tag == 'number'):
                unitNode = node[0]
                numberNode = node[1]
                del node[0]
                del node[0]
                node.append(numberNode)
                node.append(unitNode)

        # Numbers
        for numberNode in dom.xpath('//number'):
            # Avoid shortcode exercise numbers
            if (numberNode.getparent().tag == 'entry') and (numberNode.getparent().getparent().tag == 'shortcodes'):
                continue
            latexMode = etree_in_context(numberNode, 'latex')
            if (len(numberNode) == 0) and ('e' in numberNode.text):
                # Number in exponential notation: convert to <coeff> and <exp>
                numberText = numberNode.text
                float(numberText) # Check that it is really a float
                numberNode.text = None
                numberNode.append(etree.Element('coeff'))
                pos = numberText.find('e')
                numberNode[-1].text = numberText[:pos]
                numberNode.append(etree.Element('exp'))
                numberNode[-1].text = str(int(numberText[pos+1:]))

            if len(numberNode) == 0:
                # No children, means it's just a plain number
                coeffText = format_number(numberNode.text.strip())
                try:
                    if latexMode:
                        dummyNode = etree.fromstring(r'<dummy>\text{' + coeffText + '}</dummy>')
                    else:
                        dummyNode = etree.fromstring('<dummy>' + coeffText + '</dummy>')
                except etree.XMLSyntaxError, msg:
                    print repr(coeffText)
                    raise etree.XMLSyntaxError, msg
            else:
                # Scientific or exponential notation: parse out coefficient, base and exponent
                coeffNode = numberNode.find('coeff')
                expNode = numberNode.find('exp')
                baseNode = numberNode.find('base')
                if coeffNode is None:
                    # Exponential
                    if baseNode is None:
                        baseText = format_number('10')
                    else:
                        baseText = format_number(baseNode.text.strip())
                    assert expNode is not None, etree.tostring(numberNode)
                    expText = format_number(expNode.text.strip())
                    if latexMode:
                        dummyNode = etree.fromstring(r'<dummy>\text{' + baseText + r'}^{\text{' + expText + r'}}</dummy>')
                    else:
                        dummyNode = etree.fromstring('<dummy>' + baseText + '<sup>' + expText + '</sup></dummy>')
                else:
                    # Scientific notation or plain number (<coeff> only)
                    coeffText = format_number(coeffNode.text.strip())
                    if expNode is None:
                        assert baseNode is None
                        try:
                            if latexMode:
                                dummyNode = etree.fromstring(r'<dummy>\text{' + coeffText + '}</dummy>')
                            else:
                                dummyNode = etree.fromstring('<dummy>' + coeffText + '</dummy>')
                        except etree.XMLSyntaxError, msg:
                            print repr(coeffText)
                            raise etree.XMLSyntaxError, msg
                    else:
                        if baseNode is None:
                            baseText = format_number('10')
                        else:
                            baseText = format_number(baseNode.text.strip())
                        expText = format_number(expNode.text.strip())
                        if latexMode:
                            dummyNode = etree.fromstring(r'<dummy>\text{' + coeffText + r' } &#215; \text{ ' + baseText + r'}^{\text{' + expText + r'}}</dummy>')
                        else:
                            dummyNode = etree.fromstring('<dummy>' + coeffText + ' &#215; ' + baseText + '<sup>' + expText + '</sup></dummy>')
            etree_replace_with_node_list(numberNode.getparent(), numberNode, dummyNode)

        # Units
        for unitNode in dom.xpath('//unit'):
            latexMode = etree_in_context(unitNode, 'latex')
            if unitNode.text is None:
                unitNode.text = ''
            unitNode.text = unitNode.text.lstrip()
            if latexMode:
                unitNode.text = r'\text{' + unitNode.text
            if len(unitNode) == 0:
                unitNode.text = unitNode.text.rstrip()
                if latexMode:
                    unitNode.text += '}'
            else:
                if unitNode[-1].tail is None:
                    unitNode[-1].tail = ''
                unitNode[-1].tail = unitNode[-1].tail.rstrip()
                if latexMode:
                    unitNode[-1].tail += '}'
            if (unitNode.getparent().tag == 'unit_number') and (unitNode.text[0] != u'\xb0'):
                # Leave space between number and unit, except for degrees
                if latexMode:
                    unitNode.text = r'\ ' + unitNode.text
                else:
                    unitNode.text = ' ' + unitNode.text
            for sup in unitNode:
                assert sup.tag == 'sup'
                if latexMode:
                    sup.text = '$^{' + sup.text.strip() + '}$'
                    etree_replace_with_node_list(unitNode, sup, sup)
                else:
                    sup.text = sup.text.strip().replace('-', u'\u2212')
            etree_replace_with_node_list(unitNode.getparent(), unitNode, unitNode)

        # United numbers
        for node in dom.xpath('//unit_number'):
            etree_replace_with_node_list(node.getparent(), node, node)

def etree_replace_with_node_list(parent, child, dummyNode, keepTail=True):
    index = parent.index(child)
    if keepTail and (child.tail is not None):
        childTail = child.tail
    else:
        childTail = ''
    del parent[index]

    if dummyNode.text is not None:
        if index == 0:
            if parent.text is None:
                parent.text = dummyNode.text
            else:
                parent.text += dummyNode.text
        else:
            if parent[index-1].tail is None:
                parent[index-1].tail = dummyNode.text
            else:
                parent[index-1].tail += dummyNode.text

    if len(dummyNode) == 0:
        if index == 0:
            if parent.text is None:
                parent.text = childTail
            else:
                parent.text += childTail
        else:
            if parent[index-1].tail is None:
                parent[index-1].tail = childTail
            else:
                parent[index-1].tail += childTail
    else:
        if dummyNode[-1].tail is None:
            dummyNode[-1].tail = childTail
        else:
            dummyNode[-1].tail += childTail
        for i in range(len(dummyNode)-1, -1, -1):
            parent.insert(index, dummyNode[i])

def format_number(numString, decimalSeparator=',', thousandsSeparator=r'\ '):
    """
    Replace standard decimal point with new decimal separator
    (default: comma); add thousands and thousandths separators
    (default: non-breaking space).
    """
    if numString[0] in '+-':
        sign = {'+': '+', '-': '&#8722;'}[numString[0]]
        numString = numString[1:]
    else:
        sign = ''
    decimalPos = numString.find('.')
    if decimalPos == -1:
        intPart = numString
        fracPart = None
    else:
        intPart = numString[:decimalPos]
        fracPart = numString[decimalPos+1:]
    # Add thousands separator to integer part
    if len(intPart) > 4:
        pos = len(intPart)-3
        while pos > 0:
            intPart = intPart[:pos] + thousandsSeparator + intPart[pos:]
            pos -= 3
    # Add thousandths separator to fractional part
    if (fracPart is not None) and (len(fracPart) > 4):
        pos = 3
        while pos < len(fracPart):
            fracPart = fracPart[:pos] + thousandsSeparator + fracPart[pos:]
            pos += 3 + len(thousandsSeparator)
    numString = sign + intPart
    if fracPart is not None:
        numString += decimalSeparator + fracPart
    return numString




# Templates for each class here.
def delegate(element):
    '''>>> from lxml import etree
       >>> root = etree.HTML('<h1>Title</h1>')
       >>> print delegate(root[0][0])
       \chapter{Title}'''
    #print '%', element.tag, element.attrib
    # delegate the work to classes handling special cases

    # filter out empty tags


    if element.tag == 'div':
        if 'class' not in element.attrib:
            element.attrib['class'] = ''

        if element.attrib['class'] == 'keyconcepts':
            myElement = div_keyconcepts(element)
        
        elif element.attrib['class'] == 'keyquestions':
            myElement = div_keyquestions(element)
        
        elif element.attrib['class'] == 'investigation':
            myElement = div_investigation(element)
        
        elif element.attrib['class'] == 'activity':
            myElement = div_activity(element)
        
        elif element.attrib['class'] == 'newwords':
            myElement = div_newwords(element)

        elif element.attrib['class'] == 'questions':
            myElement = div_questions(element)

        elif 'investigation-' in element.attrib['class']:
            myElement = div_investigation_header(element)
        
        elif 'activity-' in element.attrib['class']:
            myElement = div_investigation_header(element)
        

        else:
            myElement = html_element(element)

    elif element.tag == 'table':
        myElement = table(element)

    elif element.tag == 'img':
        myElement = img(element)
    
    elif element.tag == 'h1':
        if 'class' not in element.attrib:
            element.attrib['class'] = ''

        if element.attrib['class'] == 'part':
            myElement = part(element)
        elif element.attrib['class'] == 'chapter':
            myElement = html_element(element)

    #
    # cnxmlplus tags 
    #

    elif element.tag == 'section':
        myElement = section(element)
    elif element.tag == '{http://www.w3.org/1998/Math/MathML}math':
        myElement = math(element)
    elif element.tag == 'worked_example':
        myElement = worked_example(element)
    elif element.tag == 'workstep':
        myElement = workstep(element)
    elif element.tag == 'list':
        myElement = listelement(element)
    elif element.tag == 'definition':
        myElement = definition(element)
    elif element.tag == 'figure':
        myElement = figure(element)
    elif element.tag == 'exercises':
        myElement = exercises(element)
    elif element.tag == 'exercise':
        myElement = exercise(element)
    elif element.tag == 'latex':
        myElement = latex(element)
#    elif element.tag == 'unit_number':
#        myElement = unitnumber(element)

    else:
        # no special handling required
        myElement = html_element(element)

    return myElement.render()


class html_element(object):
    def __init__(self, element):
        self.element = element
        
        # we make a general dict to store the contents we send to the Jinja templates.
        self.content = {}
        self.content['text'] = self.element.text if self.element.text is not None else ''
        self.content['tail'] = self.element.tail.strip() if self.element.tail is not None else ''
 
        self.content['tag'] = self.element.tag

        try:
            self.content['class'] = self.element.attrib['class']
        except KeyError:
            self.content['class'] = ''
        
        try:
            self.template = texenv.get_template(self.element.tag + '.tex')
        except TemplateNotFound:
            self.template = texenv.get_template('not_implemented.tex')
        except TypeError:
            self.template = texenv.get_template('error.tex')
#            print "Error in element: ", element 

        for a in self.element.attrib:
            self.content[a] = self.element.attrib[a]

        #escape latex characters
        self.content['text'] = escape_latex(self.content['text'])
        self.content['tail'] = escape_latex(self.content['tail'])

        self.render_children()

        
    def render(self):
        # return an empty string if the content is empty
        if self.content['text'].strip() == '':
            return ''
        else:
            return self.template.render(content=self.content)

    def render_children(self):
        for child in self.element:
            self.content['text'] += delegate(child)



class math(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        # call the xslt transform to transform mathml to latex.
        xslt = etree.parse(os.path.dirname(os.path.realpath(__file__)) + '/templates/xslt/mmltex.xsl')
        transform = etree.XSLT(xslt)
        tex = transform(element)
        tex = unicode(tex).replace('$', '')
        self.template = texenv.get_template('math.tex')
        text = escape_latex(tex) 
        # fix some things
        text = text.replace('\&', '&')
       
        # fix the autosizing bracket issue. Must have matching brackets in every math environment.
        # If they don't match, remove the autosizing \left and \right
        if text.count('\\left') != text.count('\\right'):
            text = text.replace('\\left', '').replace('\\right', '')

        # mathml tables with display
        self.content['text'] = text
        
        # replace the stackrel{^} with hat
        text = text.replace(r'\stackrel{^}', '\hat')

        #fix the trig functions too
        trigfunctions = ['sin', 'cos', 'tan', 'cot']

        # fix the \times symbol
        text = text.replace(u'×', u' \\times ')

        for tf in trigfunctions:
            text = text.replace(' ' + tf, "\\" + tf + ' ')


        self.content['text'] = text

class latex(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        text = self.content['text'].replace('$','')
        if 'begin{align' in text:
            self.content['text'] = r'$$' + self.content['text'].replace('$','') + r'$$'
        else:
            # avoid empty <latex> tags
            if self.content['text'].strip() == '':
                self.content['text'] = ' '
            self.content['text'] = '$' + self.content['text'] + '$'
        self.content['text'] = self.content['text'].replace('{align}', '{aligned}')
        self.content['text'] = self.content['text'].replace(r'\lt', r'<')

        # possible issue with $$ $$ or \[ \] modes inside a tabular.
        # test that by changing to $ $ mode
        ancestors = [a for a in element.iterancestors()]
        inside_table = ['table' in a for a in ancestors]
        if any(inside_table):
            self.content['text'] = self.content['text'].replace('$$', '$')
            self.content['text'] = self.content['text'].replace(r'\[', r'$')
            self.content['text'] = self.content['text'].replace(r'\]', r'$')

        # CNXMLPLUS files sometimes have open lines inside <latex> tags. Remove them.
        text = self.content['text']
        lines = text.split('\n')
        text = '\n'.join([l for l in lines if len(l.strip()) > 0])

        self.content['text'] = text

class worked_example(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)
        html_element.__init__(self, element)
        self.template = texenv.get_template('worked_example.tex')
        self.content['title'] = titletext


class definition(html_element):
    def __init__(self, element):
        term = element.find('.//term')
        termtext = delegate(term)
        element.remove(term)
        meaning = element.find('.//meaning')
        meaningtext = delegate(meaning)
        element.remove(meaning)
        html_element.__init__(self, element)
        self.template = texenv.get_template('definition.tex')
        self.content['term'] = termtext
        self.content['meaning'] = meaningtext

class figure(html_element):
    def __init__(self, element):
        
        # Check if the parent is a floating environment, can't nest them.
        floats = ['exercise', 'worked_example', 'activity', 'exercises']
        ancestors = [a for a in element.iterancestors()]
        inside_float = any([a.tag in floats for a in ancestors])
        print inside_float 
        # basically a floating environment
        type_element = element.find('.//type')
        typetext = 'figure'
        if type_element is not None:
            typetext = type_element.text 
            element.remove(type_element)
        html_element.__init__(self, element)
        self.template = texenv.get_template('figure.tex')
        self.content['type'] = typetext
        self.content['text'] = self.content['text'].replace(r'\par', '')


class exercise(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)
        html_element.__init__(self, element)
        self.template = texenv.get_template('exercise.tex')
        self.content['title'] = titletext

class exercises(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)

        # change the entry children to ex_entry, they conflict with tables
        for e in element.findall('./entry'):
            e.tag = 'ex_entry'

        html_element.__init__(self, element)
        self.template = texenv.get_template('exercise.tex')
        self.content['title'] = titletext


class workstep(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)
        html_element.__init__(self, element)
        self.template = texenv.get_template('workstep.tex')
        self.content['title'] = titletext

class listelement(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        try:
            list_type = element.attrib['list-type']
        except KeyError:
            list_type = 'bulleted'

        if list_type == 'enumerated':
            self.template = texenv.get_template('enumerated.tex')
        elif list_type == 'bulleted':
            self.template = texenv.get_template('bulleted.tex')
        else:
            self.template = texenv.get_template('not_implemented.tex')



class section(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)
        html_element.__init__(self, element)
        try:
            self.template = texenv.get_template('%s.tex'%element.attrib['type'])
        except KeyError:
            # We're likely inside an activity or similar
            self.template = texenv.get_template('generic_section.tex')

        self.content['title'] = titletext


class part(html_element):
    def __init__(self, element):
        r'''Convert the h1.part element to LaTeX

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('part.tex')


class unitnumber(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)

        # United numbers: ensure that units follow numbers
        for node in element:
            if (len(node) == 2) and (node[0].tag == 'unit') and (node[1].tag == 'number'):
                unitNode = node[0]
                numberNode = node[1]
                del node[0]
                del node[0]
                node.append(numberNode)
                node.append(unitNode)

class table(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        # check whether its html or cnxml table
        if element.find('.//tr') is not None:
            # html table
            # must get number of columns
            ncols = len(element.find('.//tr').findall('.//td')) + 1
            self.content['ncols'] = ncols + 1
            self.content['cols'] = '|' + '|'.join(['c' for i in range(int(ncols))]) + '|'
        else:
            #cnxml table
            if 'latex-column-spec' in element.attrib:
                self.content['columnspec'] = element.attrib['latex-column-spec']
            elif element.find('.//tgroup') is not None:
                tgroup = element.find('.//tgroup')
             #  if 'cols' in tgroup.attrib:
             #      ncols = int(tgroup.attrib['cols'])
             #      self.content['columnspec'] = '|c'*ncols + '|'
             #  else:
                ncols = len(element.find('.//row').findall('.//entry'))
                self.content['columnspec'] = '|c'*ncols + '|'
            # remove the last & in the row.
            self.content['text'] = self.content['text'].replace(r'& \\', r' \\')

            text = self.content['text'] 
            # cannot use $$ $$ or \[ \] math modes inside tabulars
            text = text.replace('$$', '$')
            text = text.replace('\\[', '$')
            text = text.replace('\\]', '$')

            self.content['text'] = text

        
        self.template = texenv.get_template('table.tex')

class img(html_element):
    def __init__(self, element):
        image_types = {'JPEG':'.jpg', 'PNG':'.png'}
        html_element.__init__(self, element)
        # get the link to the image and download it.
        src = element.attrib['src']
        name = src.rpartition('/')[-1]
        self.content['imagename'] = name

        try:
            downloaded = any([name in imname for imname in os.listdir(os.curdir + '/images')])
        except OSError:
            downloaded = False

        if not downloaded: 
            try:
                img = urllib.urlopen(src).read()
                open('images/%s'%name, 'wb').write(img)
                # now open the file and read the mimetpye
                try:
                    im = Image.open('images/%s'%name)
                    extension = image_types[im.format]
                    os.system('mv images/%s images/%s'%(name, name+extension))
                    # update the image name that the template will see
                    self.content['imagename'] = name + extension
                except:
                    print "Cannot open image: %s"%name

            except IOError:
                print "Image %s not found at %s" % (name, src)


class div_keyconcepts(html_element):
    def __init__(self, element):
        r'''Convert the div.keyconcepts element to LaTeX

        >>> from lxml import etree
        >>> root = etree.HTML('<div class="keyconcepts"></div>')
        >>> delegate(root[0][0])
        u'\n\\keyconcepts{}\n'
'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('keyconcepts.tex')


class div_keyquestions(html_element):
    def __init__(self, element):
        r'''convert the div.keyquestions element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('keyquestions.tex')


class div_questions(html_element):
    def __init__(self, element):
        r'''convert the div.questions element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('questions.tex')

class div_investigation(html_element):
    def __init__(self, element):
        r'''Convert the div.investigation element to LaTeX

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('investigation.tex')

class div_newwords(html_element):
    def __init__(self, element):
        r'''Convert the div.newwords element to LaTeX

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('newwords.tex')


class div_activity(html_element):
    def __init__(self, element):
        r'''Convert the div.activity element to LaTeX

'''
        # we need to prepare the title
        title_element = element.find('.//div[@class="activity-title"]')
        # get all the title text and remove from DOM
        title = title_element.text + ''.join([t.text for t in title_element.findall('.//')])
        element.remove(title_element)

        html_element.__init__(self, element)
        self.content['title'] = title 
        self.template = texenv.get_template('activity.tex')


class div_investigation_header(html_element):
    def __init__(self, element):
        r'''Convert the div.investigation element to LaTeX

'''
        html_element.__init__(self, element)
        self.content['title'] = self.content['class'].split('-')[1]
        self.template = texenv.get_template('investigation_header.tex')



##
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.

def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)

def escape_latex(text):
    '''Escape some latex special characters'''
    text = text.replace('&', '\&')
    text = text.replace('_', '\_')
    text = text.replace(r'%', r'\%')
    text = text.replace(r'\\%', r'\%')
    # fix some stuff
    text = text.replace(r'\rm', r'\mathrm')
    return text


def setup_texenv(loader):
    texenv = Environment(loader=loader)
    texenv.block_start_string = '((*'
    texenv.block_end_string = '*))'
    texenv.variable_start_string = '((('
    texenv.variable_end_string = ')))'
    texenv.comment_start_string = '((='
    texenv.comment_end_string = '=))'
    texenv.filters['escape_tex'] = escape_tex

    return texenv


if __name__ == "__main__":

    Textbook = True
    extension = sys.argv[1].rsplit('.')[-1]
    filename = sys.argv[1].rsplit('.')[-2].replace('/','')
    if extension == 'html':
        root = etree.HTML(open(sys.argv[1], 'r').read())
        loader = FileSystemLoader(os.path.dirname(os.path.realpath(__file__)) + '/templates/html')
        texenv = setup_texenv(loader)
        body = root.find('.//body')
    elif extension == 'cnxmlplus':
        root = etree.XML(open(sys.argv[1], 'r').read())
        transform(root) 
        loader = FileSystemLoader(os.path.dirname(os.path.realpath(__file__)) + '/templates/cnxmlplus')
        texenv = setup_texenv(loader)
        body = root.find('.//content')
    
        if Textbook:
            # remove the solution tags if its a textbook
            for e in body.findall('.//solution'):
                e.getparent().remove(e)
    else:
        print 'Unknown extension on input file type!!'
        sys.exit()
    

    print "Converting %s.%s" %(filename, extension)
    content = ''.join([delegate(element) for element in body])
    main_template = texenv.get_template('doc.tex')
    output = unicode(unescape(main_template.render(content=content))).encode('utf-8')
    open('%s.tex'%filename, 'w').write(output)
    print "Output written to %s.%s.tex"%(filename, extension)
    

