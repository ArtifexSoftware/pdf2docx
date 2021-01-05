# Minimal makefile for Sphinx documentation
#

# MODULEDIR and BUILDDIR are set in top makefile
SOURCEDIR  = .
TARGETDIR  = doctrees html

.PHONY: html clean

html: Makefile
	@sphinx-apidoc -f -e -o "$(SOURCEDIR)" "$(MODULEDIR)" && \
	sphinx-build -M html "$(SOURCEDIR)" "$(BUILDDIR)"

clean:
	@for p in $(TARGETDIR) ; do \
	    if [ -d "$(BUILDDIR)/$$p" ];  then rm -rf "$(BUILDDIR)/$$p" ; fi ; \
	done
	@if [ -e modules.rst ];  then rm modules.rst ; fi
	@if [ -e pdf2docx*.rst ];  then rm pdf2docx*.rst ; fi