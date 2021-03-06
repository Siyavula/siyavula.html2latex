# -*- coding: utf-8 -*-
#
# Convert html with special css classes to Customized LaTeX environments.
#
import sys
import os
import re, htmlentitydefs
import urllib

from lxml import etree
import jinja2
from jinja2.exceptions import TemplateNotFound


# Functions for outputting message to stderr

def warning_message(message, newLine=True):
    '''Output a warning message to stderr.'''
    sys.stderr.write('WARNING: ' + message)
    if newLine:
        sys.stderr.write('\n')

def information_message(message, newLine=True):
    '''Output an information message to stderr.'''
    sys.stderr.write('INFO: ' + message)
    if newLine:
        sys.stderr.write('\n')

def error_message(message, newLine=True, terminate=True):
    global commandlineArguments
    sys.stderr.write('ERROR: ' + message)
    if newLine:
        sys.stderr.write('\n')
    if terminate:
        sys.exit()


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


# 

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
    # delegate the work to classes handling special cases

    # Filter out empty tags
    try:
        temp = element.tag
    except AttributeError:
        warning_message("Could not determine tag of element: %s"%(repr(element)))

    if element.tag == 'div':
        if 'class' not in element.attrib:
            element.attrib['class'] = ''

        if element.attrib['class'] == 'keyconcepts':
            myElement = div_keyconcepts(element)
        
        elif element.attrib['class'] == 'keyquestions':
            myElement = div_keyquestions(element)

        elif element.attrib['class'] == 'question':
            myElement = div_question(element)

        elif element.attrib['class'] == 'example':
            myElement = div_example(element)

        elif element.attrib['class'] == 'casestudy':
            myElement = div_casestudy(element)

        elif element.attrib['class'] == 'exproblem':
            myElement = div_exproblem(element)

        elif element.attrib['class'] == 'exsolution':
            myElement = div_exsolution(element)
        
        elif element.attrib['class'] == 'answer':
            myElement = div_answer(element)

        elif element.attrib['class'] == 'investigation':
            myElement = div_investigation(element)
        
        elif element.attrib['class'] == 'activity':
            myElement = div_activity(element)
        
        elif element.attrib['class'] == 'newwords':
            myElement = div_newwords(element)

        elif element.attrib['class'] == 'didyouknow':
            myElement = div_didyouknow(element)

        elif element.attrib['class'] == 'questions':
            myElement = div_questions(element)

        elif element.attrib['class'] == 'project':
            myElement = div_project(element)

        elif element.attrib['class'] == 'aside':
            myElement = div_aside(element)

        elif element.attrib['class'] == 'note':
            myElement = div_note(element)

        elif element.attrib['class'] == 'warning':
            myElement = div_warning(element)

        elif element.attrib['class'] == 'teachersguide':
            myElement = div_teachersguide(element)

        elif element.attrib['class'] == 'visit':
            myElement = div_visit(element)
        
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
    elif element.tag == 'a':
        myElement = a(element)
    
    elif element.tag == 'h1':
        if 'class' not in element.attrib:
            element.attrib['class'] = ''
        elif element.attrib['class'] == '':
            myElement = html_element(element)
        elif element.attrib['class'] == 'part':
            myElement = part(element)
        elif element.attrib['class'] == 'chapter':
            myElement = html_element(element)

        else:
            myElement = html_element(element)

    #
    # cnxmlplus tags 
    #
    elif  element.tag == 'note':
        myElement = note(element)
    elif element.tag == 'activity':
        myElement = activity(element)
    elif element.tag == 'link':
        myElement = link(element)
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
    elif element.tag in ['latex', 'chem_compound', 'spec_note']:
        myElement = latex(element)
    elif element.tag in ['pspicture', 'tikzpicture']:
        myElement = pstikzpicture(element)
    elif element.tag == 'image':
        myElement = image(element)

    elif isinstance(element, etree._Comment):
        myElement = None # skip XML comments
    else:
        # no special handling required
        myElement = html_element(element)

    try:
        myElement
    except NameError:
        error_message("Error with element!! %s\n\n"%etree.tostring(element), terminate=False)
        return ''

    if myElement is None:
        return ''
    else:
        return myElement.render()


class html_element(object):
    def __init__(self, element):
        self.element = element
        
        # we make a general dict to store the contents we send to the Jinja templates.
        self.content = {}
        self.content['text'] = self.element.text if self.element.text is not None else ''
        tail = self.element.tail if self.element.tail is not None else ''
        if (len(tail) > 0) and (tail[0] in [' \t\r\n']):
            tail = ' ' + tail.lstrip()
        if (len(tail) > 0) and (tail[-1] in [' \t\r\n']):
            tail = tail.rstrip() + ' '
        self.content['tail'] = tail
 
        self.content['tag'] = escape_latex(self.element.tag)

        try:
            self.content['class'] = self.element.attrib['class']
        except KeyError:
            self.content['class'] = ''
        
        try:
            self.template = texenv.get_template(self.element.tag + '.tex')
        except TemplateNotFound:
            self.template = texenv.get_template('not_implemented.tex')
        except TypeError:
            error_message("Error in element: " + repr(element), terminate=False)
            self.template = texenv.get_template('error.tex')

        for a in self.element.attrib:
            self.content[a] = self.element.attrib[a]

        #escape latex characters

        self.content['text'] = clean(self.content['text'])
        self.content['text'] = escape_latex(self.content['text'])
        self.content['tail'] = escape_latex(self.content['tail'])

        self.content['text'] = clean(self.content['text'])

        self.render_children()

        
    def render(self):
        # return an empty string if the content is empty
#        if self.content['text'].strip() == '':
#            return ''
#        else:
            return self.template.render(content=self.content)

    def render_children(self):
        for child in self.element:
            self.content['text'] += delegate(child)

    def remove_empty(self):
        '''Must remove empty tags'''
        pass

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
        # align, align*, equation, equation*, eqnarray, eqnarray*
        #import pdb
        #pdb.set_trace()

        html_element.__init__(self, element)
        text = unescape_latex(self.content['text'].strip()) # Undo escaping since this is already latex

        attribDisplay = element.attrib.get('display', 'inline')
        if attribDisplay == 'inline':
            text = r'\(' + text + r'\)'
        elif attribDisplay == 'block':
            foundMathEnvironment = False
            for environmentName in ['align', 'align*', 'equation', 'equation*', 'eqnarray', 'eqnarray*']:
                substr = r'\begin{%s}'%environmentName
                if text[:len(substr)] == substr:
                    foundMathEnvironment = True
                    break
            if not foundMathEnvironment:
                text = '\\[\n' + text + '\n\\]\n'
            else:
                text += '\n'
        else:
            raise ValueError, "Unknown value for 'display' attribute in <latex> element: " + repr(attribDisplay)

        # possible issue with $$ $$ or \[ \] modes inside a tabular.
        # test that by changing to $ $ mode
        ancestors = [a for a in element.iterancestors()]
        inside_table = ['table' in a for a in ancestors]
        if any(inside_table):
            text = text.replace(r'\[', r'\(')
            text = text.replace(r'\]', r'\)')

        # CNXML+ files sometimes have open lines inside <latex> tags. Remove them.
        lines = text.split('\n')
        text = '\n'.join([l for l in lines if len(l.strip()) > 0])
        
        text = text.replace('\&', '&')
        text = text.replace(r'\_', '_')

        self.content['text'] = text

class pstikzpicture(html_element):
    def __init__(self, element):
        codeElement = element.find('code')
        element.text = codeElement.text
        element.remove(codeElement)
        for child in codeElement.getchildren():
            element.append(child)
        html_element.__init__(self, element)
        self.content['text'] = unescape_latex(self.content['text'].strip()) # Undo escaping since this is already latex


class worked_example(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)
        html_element.__init__(self, element)
        self.template = texenv.get_template('worked_example.tex')
        self.content['title'] = titletext


class note(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)

        if 'type' in element.attrib.keys():
            self.content['type'] = element.attrib['type']
        else:
            self.content['type'] = 'note'

        self.template = texenv.get_template('note.tex')

class activity(html_element):
    def __init__(self, element):
         
        title = element.find('.//title')
        if title is not None:
            title_text = delegate(title)
            element.remove(title)
        else:
            title_text = ''

        html_element.__init__(self, element)
        self.content['title'] = title_text

        if 'type' in element.attrib.keys():
            self.content['type'] = element.attrib['type']
        else:
            self.content['type'] = 'activity'
       

        self.template = texenv.get_template('activity.tex')



class link(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        # make it a url if the 'href' attribute is set
        attributes = element.attrib.keys()
        if 'url' in attributes:
            self.content['url'] = escape_latex(element.attrib['url'])
        elif 'target-id' in attributes:
            self.content['target_id'] = escape_latex(element.attrib['target-id'])
            self.template = texenv.get_template('link-reference.tex')
        else:
            self.content['url'] = escape_latex(self.content['text'])




class a(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        # make it a url if the 'href' attribute is set
        if 'href' in element.attrib.keys():
            self.content['url'] = element.attrib['href']
        else:
            self.content['url'] = self.content['text']
            



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
        if title is not None:
            titletext = delegate(title)
            element.remove(title)
        else: titletext = ""
        html_element.__init__(self, element)
        self.template = texenv.get_template('exercise.tex')
        self.content['title'] = titletext

class exercises(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = None
        if title is not None:
            titletext = delegate(title)
            element.remove(title)

        # change the entry children to ex_entry, they conflict with tables
        for e in element.findall('./entry'):
            e.tag = 'ex_entry'

        html_element.__init__(self, element)
        self.template = texenv.get_template('exercise.tex')
        if titletext is not None:
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

        sectiondepth = {0:'chapter', 1:'section', 2:'subsection', 3:'subsubsection', 4:'textbf'}
        try:
            self.template = texenv.get_template('%s.tex'%element.attrib['type'])
        except KeyError:
            # find the depth of the section.
            depth = 0
            for a in element.iterancestors():
                if a.tag == 'section': depth += 1

            self.template = texenv.get_template('%s.tex'%sectiondepth[depth])

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
            # must get number of columns. # find maximum number of td elements in a single row
            max_td = 0
            for row in element.findall('.//tr'):
                ncols = len(row.findall('.//td'))
                max_td = max([max_td, ncols])
                ncols = len(row.findall('.//th'))
                max_td = max([max_td, ncols])

            self.content['ncols'] = max_td
            ncols = max_td
            
            # try a fancy column specifier for longtable
            colspecifier = r">{\centering}p{%1.3f\textwidth}"%(float(0.85/ncols))
            self.content['cols'] = '|' + '|'.join([colspecifier for i in range(int(ncols))]) + '|'
            self.content['text'] = self.content['text'].replace(r'& \\ \hline', r'\tabularnewline \hline')
            self.content['text'] = self.content['text'].replace('\\par', ' ')
            self.content['text'] = self.content['text'].replace('\n','').replace('\\hline','\hline\n')
            #self.content['text'] = ''
        else:
            #cnxml table
            # must get number of columns. # find maximum number of td elements in a single row
            max_td = 0
            for row in element.findall('.//row'):
                ncols = len(row.findall('.//entry'))
                max_td = max([max_td, ncols])

            self.content['ncols'] = max_td
            ncols = max_td
            
            if 'latex-column-spec' in element.attrib:
                self.content['columnspec'] = element.attrib['latex-column-spec']
            elif element.find('.//tgroup') is not None:

                colspecifier = r">{\raggedright}p{%1.3f\textwidth}"%(float(0.85/ncols))
                self.content['columnspec'] = '|' + '|'.join([colspecifier for i in range(int(ncols))]) + '|'
#               tgroup = element.find('.//tgroup')
#            #  if 'cols' in tgroup.attrib:
#            #      ncols = int(tgroup.attrib['cols'])
#            #      self.content['columnspec'] = '|c'*ncols + '|'
#            #  else:
#               ncols = len(element.find('.//row').findall('.//entry'))
#               self.content['columnspec'] = '|c'*ncols + '|'
            # remove the last & in the row.

            # fix some stuff

            self.content['text'] = self.content['text'].replace(r'& \\', r' \\')
            self.content['text'] = self.content['text'].replace(r'& \tabularnewline', r' \tabularnewline')
            text = self.content['text'] 
            # cannot use $$ $$ or \[ \] math modes inside tabulars
            text = text.replace('$$', '$')
            text = text.replace('\\[', '$')
            text = text.replace('\\]', '$')
            text = text.replace('\\begin{center}', '').replace('\\end{center}', '')
            text = text.replace('\\par', '')
            text = text.replace('\n\n', '')

            
            # fix image widths if they are present
            lines = text.split('\n')
            new_lines = []
            for l in lines:
                if 'includegraphics' in l:
                    if ncols is not None:
                        start = ''.join(l.partition('[')[0:2])
                        middle = r'width=%1.3f\textwidth'%(float(0.75/ncols))
                        end = ''.join(l.rpartition(']')[-2:])
                        l = ''.join([start, middle, end])

                new_lines.append(l)

            text = '\n'.join(new_lines)


            self.content['text'] = text

        
        
        self.template = texenv.get_template('table.tex')



class img(html_element):
    def __init__(self, element):
        image_types = {'JPEG':'.jpg', 'PNG':'.png', 'GIF':'.gif'}
        html_element.__init__(self, element)
        # get the link to the image and download it.
        src = element.attrib['src']
        name = src.rpartition('/')[-1]
        self.content['imagename'] = src
        self.template = texenv.get_template('img.tex')
        
#       try:
#           downloaded = any([name in imname for imname in os.listdir(os.curdir + '/images')])
#       except OSError:
#           try:
#               downloaded = any([name in imname for imname in os.listdir(os.curdir + '/')])
#           except OSError:
#               downloaded = False
#           downloaded = False

#       if not downloaded: 
#           try:
#               img = urllib.urlopen(src).read()
#               open('images/%s'%name, 'wb').write(img)
#               # now open the file and read the mimetpye
#               try:
#                   im = Image.open('images/%s'%name)
#                   extension = image_types[im.format]
#                   os.system('mv images/%s images/%s'%(name, name+extension))
#                   # update the image name that the template will see
#                   self.content['imagename'] = name + extension
#               except:
#                   print "Cannot open image: %s"%name

#           except IOError:
#               print "Image %s not found at %s" % (name, src)


class image(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        specifier = 'width=0.8\\textwidth'
        self.content['specifier'] = specifier
        src = element.find('.//src')
        if src is not None:
            self.content['src'] = src.text
#       if ('width' in self.content.keys()) and ('height' in self.content.keys()):
#           width = float(self.content['width'])/72.
#           height = float(self.content['height'])/72.
#           if width > 4.0:
#               self.content['specifier'] = r'width=4in'
#           else:
#               self.content['specifier'] = r'width=%1.2fin, height=%1.2fin'%(width, height)


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

class div_aside(html_element):
    def __init__(self, element):
        r'''convert the div.aside element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('aside.tex')

class div_note(html_element):
    def __init__(self, element):
        r'''convert the div.note element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('note.tex')

class div_warning(html_element):
    def __init__(self, element):
        r'''convert the div.warning element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('warning.tex')

class div_casestudy(html_element):
    def __init__(self, element):
        r'''convert the div.casestudy element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('casestudy.tex')

class div_visit(html_element):
    def __init__(self, element):
        r'''convert the div.visit element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('visit.tex')

class div_didyouknow(html_element):
    def __init__(self, element):
        r'''convert the div.didyouknow element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('didyouknow.tex')

        
class div_project(html_element):
    def __init__(self, element):
        r'''convert the div.project element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('project.tex')

class div_questions(html_element):
    def __init__(self, element):
        r'''convert the div.questions element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('questions.tex')


class div_answer(html_element):
    def __init__(self, element):
        r'''convert the div.answer element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('answer.tex')

class div_example(html_element):
    def __init__(self, element):
        r'''convert the div.example element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('example.tex')

class div_exproblem(html_element):
    def __init__(self, element):
        r'''convert the div.exproblem element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('exproblem.tex')


class div_exsolution(html_element):
    def __init__(self, element):
        r'''convert the div.exsolution element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('exsolution.tex')

class div_question(html_element):
    def __init__(self, element):
        r'''convert the div.question element to latex

'''
        # get the answer element
        answer = element.find('.//div[@class="answer"]')
        html_element.__init__(self, element)
#       if answer is not None:
#           answertext = delegate(answer)
#           element.remove(answer)
#           html_element.__init__(self, element)
#           self.content['answer'] = answertext
#       else:
#           html_element.__init__(self, element)
#           self.content['answer'] = ''

        self.template = texenv.get_template('question.tex')
        


class div_teachersguide(html_element):
    def __init__(self, element):
        r'''convert the div.teachersguide element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('teachersguide.tex')

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
        if title_element is not None: 
            try:
                title = title_element.text + ''.join([t.text for t in title_element.findall('.//')])
            except TypeError:
                title= ''
            element.remove(title_element)
        else:
            title = 'None'
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
    text = text.replace(r'&', r'\&')
    text = text.replace(r'#', r'\#')
    text = text.replace(r'_', r'\_')
    text = text.replace(r'%', r'\%')
    text = text.replace(r'\\%', r'\%')
    text = text.replace(r'\\%', r'\%')
    # fix some stuff
    text = text.replace(r'\rm', r'\mathrm')
    return text

def unescape_latex(text):
    text = text.replace(r'\%', r'%')
    text = text.replace(r'\_', r'_')
    text = text.replace(r'\#', r'#')
    text = text.replace(r'\&', r'&')
    return text


def setup_texenv(loader):
    texenv = jinja2.Environment(loader=loader)
    texenv.block_start_string = '((*'
    texenv.block_end_string = '*))'
    texenv.variable_start_string = '((('
    texenv.variable_end_string = ')))'
    texenv.comment_start_string = '((='
    texenv.comment_end_string = '=))'
    texenv.filters['escape_tex'] = escape_tex

    return texenv

def clean(text):
    text = text.replace(u'Â', ' ')
    text = text.replace(u'â', '')
    text = text.replace(u'â', '')
    text = text.replace(u'''
''', '\n')
    text = text.replace(u'â', '\'')
    text = text.replace(u'â', '')
    text = text.replace(u'â', '``')
    text = text.replace(u'â ', '\'\'')
    text = text.replace(u'\u00a0', ' ')
    text = text.replace(u'\u00c2', ' ')
    return text

if __name__ == "__main__":

    Textbook = True
    extension = sys.argv[1].rpartition('.')[-1]
    filename = sys.argv[1].rpartition('.')[-3]
    information_message(extension + ' ' + filename)
    if extension == 'html':
        f = open(sys.argv[1], 'r').read().decode('utf-8')
        if f.strip() == '':
            fout = open(sys.argv[1].replace('.html', '.tex'), 'w')
            fout.write('''%empty input file''')
            fout.close()
            sys.exit()
        try:
            root = etree.HTML(open(sys.argv[1], 'r').read())
        except:
            error_message(sys.argv[1] + " not valid")

        loader = jinja2.FileSystemLoader(os.path.dirname(os.path.realpath(__file__)) + '/templates/html')
        texenv = setup_texenv(loader)
        body = root.find('.//body')
    elif (extension == 'cnxmlplus') or (extension == 'cnxml'):
        root = etree.XML(open(sys.argv[1], 'r').read())
        transform(root) 
        loader = jinja2.FileSystemLoader(os.path.dirname(os.path.realpath(__file__)) + '/templates/cnxmlplus')
        texenv = setup_texenv(loader)
        body = root.find('.//content')
#       if Textbook:
#           # remove the solution tags if its a textbook
#           for e in body.findall('.//solution'):
#               if type(e) is not NoneType:
#                   e.getparent().remove(e)
    else:
        error_message('Unknown extension on input file type!')

    information_message("Converting %s.%s" %(filename, extension))
    content = ''.join([delegate(element) for element in body])
    main_template = texenv.get_template('doc.tex')
    output = unicode(unescape(main_template.render(content=content))).encode('utf-8').replace(r'& \\ \hline', r'\\ \hline')
    #output = clean(output)
    open('%s.tex'%filename, 'w').write(output)
    information_message("Output written to %s.%s.tex"%(filename, extension))
