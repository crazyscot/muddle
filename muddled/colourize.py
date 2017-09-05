# -*- coding: utf-8 -*-
"""
Output colourisation
Inspired by colorgcc, this makes long gcc output easier on the eye.
(Why yes, I do know about gcc 4.9's ability to colour to the terminal.  But in
this muddled world, gcc is not outputting to a tty, so doesn't colourise.  To
force it, you'd have to set a cflag in every last package, so it's much better
to do this centrally. Doing it this way also picks up gcc-like errors from
other tools.)
"""

import os
import re
import sys
from collections import defaultdict,Container

# Requires colorama to be able to colour, but won't fall over if it's not there.
# - 'apt install python-colorama' or 'pip install colorama'
try:
    from colorama import Fore, Back, Style

    colour = {
        # These are all the styles we might set
        'reset': Style.RESET_ALL,
        'filename': Fore.WHITE + Style.BRIGHT,
        'line_num': Fore.WHITE + Style.BRIGHT,
        'line_pos': Fore.WHITE + Style.BRIGHT,
        'quoted': Fore.WHITE + Style.BRIGHT,

        'error': Fore.RED + Style.BRIGHT,
        'warning': Fore.MAGENTA + Style.BRIGHT,
        'note': Fore.CYAN,
        'intro': Fore.CYAN,
        'introquote': Fore.CYAN,
        }
    have_colour = True
except ImportError:
    # Quietly fall back to uncoloured behaviour
    colour = defaultdict(lambda:'')
    have_colour = False

if os.getenv('MUDDLE_COLOURISE') == 'html':
    # Alternate mode for HTML output.. wrap text up in CSS classes
    class htmlcolour(Container):
        def __getitem__(self, key):
            if key=='reset':
                return '</span>'
            return '<span class="%s">'%key
        def __contains__(self):
            return True
    colour = htmlcolour()
    have_colour = True

def wrap_colour(string, col):
    ''' Colourises a string '''
    return colour[col] + string + colour['reset']

def colour_quote(string, inside):
    ''' colourises things found between quotes and smart quotes
        @inside@ is a member of the colour dict, it is applied to whatever is found inside quotes
    '''
    # blah blah `thing to highlight' blah
    string = re.sub(r'`([^\']+)\'', '`' + colour[inside] + r'\1' + colour['reset'] + "'", string)
    # blah blah ‘smart quoted thing’ blah
    string = re.sub(r'‘([^’]+)’', '‘' + colour[inside] + r'\1' + colour['reset'] + '’', string)
    # sometimes gcc doesn't even bother with the backquote when muddle is capturing the output?
    string = re.sub(r'\'([^\']+)\'', '\'' + colour[inside] + r'\1' + colour['reset'] + "'", string)
    return string

# map keywords to colours
gcc_keywords = {
        'error:' : 'error',
        'warning:' : 'warning',
        'note:' : 'note',
        'instantiated from' : 'intro',
        'undefined reference' : 'error',
        'multiple definition of' : 'error',
        }

def keyword_map(string, mapdict):
    ''' Colourises keywords in a string '''
    for k in mapdict:
        string = string.replace(k, wrap_colour(k, mapdict[k]))
    return string

def colour_filename(filename):
    ''' Part-colourises a filename.
        (Muddle paths are often quite long and dangly, and we generally aren't
        interested in all of them.)
    '''
    parts = filename.split('/')
    # We'll colour up to 3 components.
    limit = min(3, len(parts))
    for i in range(-limit,0):
        parts[i] = wrap_colour(parts[i], 'filename')
    return '/'.join(parts)

def colour_gcc(reresult):
    ''' Colourises gcc and gcc-like output.
        @reresult@ is a regexp match.
        groups 1 and 2 are filename and line number.
        group 3 is the position in the line, may not be present.
        group 4 is the rest of the line - scan for keywords and smart quotes.
    '''
    (filename, lineno, linepos, msg) = reresult.group(1,2,3,4)
    if linepos is not None:
        linepos = wrap_colour(linepos, 'line_pos') + ':'
    else:
        linepos = ''
    msg = keyword_map(msg, gcc_keywords)
    msg = colour_quote(msg, 'quoted')
    return colour_filename(filename) + ':' + wrap_colour(lineno, 'line_num') + ':' + linepos + msg

def colour_one_line(l):
    # Deal with most gcc and gcc-like output, including linker errors:
    result = re.search(r'^(.+?\.[^:/ ]+):([0-9]+):([0-9]+)?:?(.*)$', l) # file:line[:pos]:msg
    if result:
        return colour_gcc(result)
    # Otherwise, look for introductions: In function 'int blah(void)':
    return colour_quote(l, 'introquote')

def colourize(msg):
    ''' Colourizes a multi-line message '''
    sw = os.getenv('MUDDLE_COLOURISE', 'auto')
    if sw=='auto':
        sw = '1' if sys.stdout.isatty() else '0'
    if not (sw.lower() in ('yes','y','true','1','html')):
        # we're not enabled, do nothing
        return msg
    output = []
    if not have_colour:
        return str(msg) + '''

(muddle says: By the way, I would have colourised this output but you don\'t
 have the colorama package installed.
 `apt install python-colorama' or `pip install colorama' to make it work.
 Or set MUDDLE_COLOURISE=no in your environment to shut this message up.)'''

    lines = str(msg).splitlines(True)
    output = []
    for l in lines:
        output.append( colour_one_line(l.strip()) +'\n')
    return ''.join(output)
