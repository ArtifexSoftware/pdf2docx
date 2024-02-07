# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import datetime
sys.path.insert(0, os.path.abspath("../pdf2docx/"))


# -- Project information -----------------------------------------------------

project = 'pdf2docx'
thisday = datetime.date.today()
copyright = str(thisday.year) + ", Artifex"
author = 'Artifex Software, Inc.'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The full version, including alpha/beta/rc tags.
def get_version(fname):
    if os.path.exists(fname):
        with open(fname, 'r') as f:
            release = f.readline().strip()
    else:
        release = 'alpha'

    return release

version = get_version('../version.txt')

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinxcontrib.apidoc',
    'sphinx_copybutton'
]

apidoc_module_dir = '../pdf2docx'
apidoc_output_dir = 'api'
apidoc_excluded_paths = []
apidoc_separate_modules = True

# Add any paths that contain templates here, relative to this directory.
# templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [    
]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'furo'


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# A list of CSS files. The entry must be a filename string or a tuple containing
# the filename string and the attributes dictionary. The filename must be
# relative to the html_static_path, or a full URI
html_css_files = ["custom.css"]


html_favicon = "_static/PyMuPDF.ico"


# -- Options for LaTeX output ---------------------------------------------
latex_elements = {
    # "fontpkg": r"\usepackage[sfdefault]{ClearSans} \usepackage[T1]{fontenc}"
}
# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [("index", "pdf2docx.tex", "pdf2docx Documentation", "Artifex", "manual")]
# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = "images/pymupdf-logo.png"

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
# latex_use_parts = False

# If true, show page references after internal links.
latex_show_pagerefs = False

# If true, show URL addresses after external links.
# latex_show_urls = True
# latex_use_xindy = True
# Documents to append as an appendix to all manuals.
# latex_appendices = []

# If false, no module index is generated.
latex_domain_indices = True

# -- Options for PDF output --------------------------------------------------
# Grouping the document tree into PDF files. List of tuples
# (source start file, target name, title, author).

pdf_documents = [("index", "pdf2docx", "pdf2docx manual", "Artifex")]

# A comma-separated list of custom stylesheets. Example:
# pdf_stylesheets = ["sphinx", "bahnschrift", "a4"]

# Create a compressed PDF
pdf_compressed = True

# A colon-separated list of folders to search for fonts. Example:
# pdf_font_path=['/usr/share/fonts', '/usr/share/texmf-dist/fonts/']

# Language to be used for hyphenation support
pdf_language = "en_US"

# If false, no index is generated.
pdf_use_index = True

# If false, no modindex is generated.
pdf_use_modindex = True

# If false, no coverpage is generated.
pdf_use_coverpage = True

pdf_break_level = 2

pdf_verbosity = 0
pdf_invariant = True



